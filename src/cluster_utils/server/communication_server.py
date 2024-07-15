from __future__ import annotations

import asyncio
import logging
import pickle
import signal
import socket
import threading
import time

from cluster_utils.base import constants
from cluster_utils.base.communication import MessageTypes

from .job import JobStatus


class DatagramProtocol:
    """Protocol class for receiving UDP messages from the jobs."""

    def __init__(self, server: CommunicationServer):
        self.server = server

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if data is not None:
            self.server.handle_message(data)


class CommunicationServer:
    def __init__(self, cluster_system):
        logger = logging.getLogger("cluster_utils")
        self.event_loop = None
        self.ip_adress = self.get_own_ip()
        self.port = None
        self.cluster_system = cluster_system

        self.handlers = {
            MessageTypes.JOB_STARTED: self.handle_job_started,
            MessageTypes.ERROR_ENCOUNTERED: self.handle_error_encountered,
            MessageTypes.JOB_SENT_RESULTS: self.handle_job_sent_results,
            MessageTypes.JOB_CONCLUDED: self.handle_job_concluded,
            MessageTypes.EXIT_FOR_RESUME: self.handle_exit_for_resume,
            MessageTypes.JOB_PROGRESS_PERCENTAGE: self.handle_job_progress,
            MessageTypes.METRIC_EARLY_REPORT: self.handle_metric_early_report,
        }

        logger.info(f"Master script running on IP: {self.ip_adress}")
        self.start_listening()

    @property
    def connection_info(self):
        if self.ip_adress is None or self.port is None:
            raise ValueError("Either IP adress or port are not known yet.")
        return {"ip": self.ip_adress, "port": self.port}

    def get_own_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def start_listening(self):
        logger = logging.getLogger("cluster_utils")

        self.event_loop = asyncio.get_event_loop()

        # create UDP server
        coroutine = self.event_loop.create_datagram_endpoint(
            lambda: DatagramProtocol(self),
            # setting port to 0 makes it automatically pick a free port
            local_addr=(self.ip_adress, 0),
        )
        transport, _ = self.event_loop.run_until_complete(coroutine)

        # get the port it chose from the underlying socket object
        socket = transport.get_extra_info("socket")
        self.port = socket.getsockname()[1]
        logger.info(f"Communication happening on port: {self.port}")

        # register a signal handler to stop the event loop on SIGINT
        self.event_loop.add_signal_handler(signal.SIGINT, self.event_loop.stop)

        t = threading.Thread(target=self.event_loop.run_forever, daemon=True)
        t.start()

    def handle_job_started(self, message):
        logger = logging.getLogger("cluster_utils")
        job_id, hostname = message
        logger.info(f"Job {job_id} started on hostname {hostname}")
        job = self.cluster_system.get_job(job_id)
        if job is None:
            raise ValueError(
                "Received a start-message from a job that is not listed in the cluster"
                " interface system"
            )
        job.status = JobStatus.RUNNING
        job.hostname = hostname
        if not job.waiting_for_resume:
            job.start_time = time.time()
        job.waiting_for_resume = False

    def handle_error_encountered(self, message):
        logger = logging.getLogger("cluster_utils")
        job_id, strings = message
        logger.warning(f"Job {job_id} died with error {strings[-1:]}.")
        job = self.cluster_system.get_job(job_id)
        if job is None:
            raise ValueError(
                "Job was not in the list of jobs but encountered an error... fucked up"
                " twice, huh?"
            )
        job.status = JobStatus.FAILED
        job.error_info = "".join(strings)

    def handle_job_sent_results(self, message):
        logger = logging.getLogger("cluster_utils")
        job_id, metrics = message
        job = self.cluster_system.get_job(job_id)
        if job is None:
            raise ValueError(
                "Received a results-message from a job that is not listed in the"
                " cluster interface system"
            )
        if job.status == JobStatus.CONCLUDED_WITHOUT_RESULTS:
            job.status = JobStatus.CONCLUDED
            logger.info(f"Job {job_id} now sent results after concluding earlier.")
        else:
            job.status = JobStatus.SENT_RESULTS
            logger.info(f"Job {job_id} sent results.")
        job.metrics = metrics
        job.set_results()
        if job.get_results() is None:
            raise ValueError("Job sent metrics but something went wrong")

    def handle_job_concluded(self, message):
        logger = logging.getLogger("cluster_utils")
        (job_id,) = message
        job = self.cluster_system.get_job(job_id)
        if job is None:
            raise ValueError(
                "Received a job-concluded-message from a job that is not listed in the"
                " cluster interface system"
            )
        if job.status != JobStatus.SENT_RESULTS or job.get_results() is None:
            # It is possible that the CONCLUDED message is processed before the SENT_RESULTS
            # message. We catch that case here by moving the job to an intermediate concluded state
            # and that is either changed to CONCLUDED when the SENT_RESULTS message arrives, or to
            # FAILED when a certain time passes without any received results.
            job.status = JobStatus.CONCLUDED_WITHOUT_RESULTS

            def fail_job_if_still_no_results():
                if job.status == JobStatus.CONCLUDED_WITHOUT_RESULTS:
                    job.status = JobStatus.FAILED
                    job.error_info = "Job concluded but sent no results."
                    logger.info(
                        f"Job {job_id} has concluded, but has not sent results after"
                        f" {constants.CONCLUDED_WITHOUT_RESULTS_GRACE_TIME_IN_SECS} seconds."
                        " Considering job failed."
                    )

            # We give the job some time to send its results and fail it otherwise.
            self.event_loop.call_later(
                constants.CONCLUDED_WITHOUT_RESULTS_GRACE_TIME_IN_SECS,
                fail_job_if_still_no_results,
            )
            logger.info(
                f"Job {job_id} announced its end but no results were sent so far."
            )
        else:
            job.status = JobStatus.CONCLUDED
            logger.info(f"Job {job_id} finished successfully.")

    def handle_exit_for_resume(self, message):
        logger = logging.getLogger("cluster_utils")
        (job_id,) = message
        logger.info(f"Job {job_id} exited to be resumed.")

        job = self.cluster_system.get_job(job_id)
        self.cluster_system.resume(job)

    def handle_job_progress(self, message):
        logger = logging.getLogger("cluster_utils")
        job_id, percentage_done = message
        logger.info(f"Job {job_id} announced it is {int(100 * percentage_done)}% done.")
        job = self.cluster_system.get_job(job_id)
        if 0 < percentage_done <= 1:
            job.estimated_end = (
                job.start_time + (time.time() - job.start_time) / percentage_done
            )

    def handle_metric_early_report(self, message):
        logger = logging.getLogger("cluster_utils")
        job_id, metrics = message
        logger.info(f"Job {job_id} sent intermediate results.")
        job = self.cluster_system.get_job(job_id)
        if job.metric_to_watch in metrics:
            logger.info(
                f"Job {job_id} currently has"
                f" {job.metric_to_watch}={metrics[job.metric_to_watch]}."
            )
            job.reported_metric_values = job.reported_metric_values or []
            job.reported_metric_values.append(metrics[job.metric_to_watch])

    def handle_message(self, pickled_data: bytes) -> None:
        """Handle a pickled message."""
        msg_type_idx, message = pickle.loads(pickled_data)

        if msg_type_idx in self.handlers:
            self.handlers[msg_type_idx](message)
        else:
            logger = logging.getLogger("cluster_utils")
            logger.error(
                "Received invalid message: type: %s, message: %s, raw data: %s.",
                msg_type_idx,
                message,
                pickled_data,
            )
