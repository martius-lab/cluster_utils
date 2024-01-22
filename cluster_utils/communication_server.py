import logging
import pickle
import signal
import socket
import threading
import time

import pyuv

from . import constants
from .job import JobStatus


class MessageTypes:
    JOB_STARTED = 0
    ERROR_ENCOUNTERED = 1
    JOB_SENT_RESULTS = 2
    JOB_CONCLUDED = 3
    EXIT_FOR_RESUME = 4
    JOB_PROGRESS_PERCENTAGE = 5
    METRIC_EARLY_REPORT = 6


class MinJob:
    def __init__(self, job_id, settings, status):
        self.id = job_id
        self.settings = settings
        self.status = status
        self.metrics = None


class CommunicationServer:
    def __init__(self, cluster_system):
        logger = logging.getLogger("cluster_utils")
        self.event_loop = None
        self.ip_adress = self.get_own_ip()
        self.port = None
        logger.info(f"Master script running on IP: {self.ip_adress}")
        self.start_listening()
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

        def on_read(handle, ip_port, flags, data, error):
            if data is not None:
                # handle.send(ip_port, data) This would be a way to ensure messaging
                # worked well
                msg_type_idx, message = pickle.loads(data)
                if msg_type_idx not in self.handlers:
                    self.handle_unidentified_message(data, msg_type_idx, message)
                else:
                    self.handlers[msg_type_idx](message)

        def async_exit(async_connection):
            async_connection.close()
            signal_h.close()
            server.close()

        self.event_loop = pyuv.Loop.default_loop()
        async_connection = pyuv.Async(self.event_loop)

        def signal_cb(sig, frame):
            async_connection.send(async_exit)

        server = pyuv.UDP(self.event_loop)
        server.bind((self.ip_adress, 0))
        self.port = server.getsockname()[1]
        logger.info(f"Communication happening on port: {self.port}")
        server.start_recv(on_read)

        signal_h = pyuv.Signal(self.event_loop)
        signal_h.start(signal_cb, signal.SIGINT)

        t = threading.Thread(target=self.event_loop.run, daemon=True)
        t.start()

        signal.signal(signal.SIGINT, signal_cb)

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

            def fail_job_if_still_no_results(timer):
                if job.status == JobStatus.CONCLUDED_WITHOUT_RESULTS:
                    job.status = JobStatus.FAILED
                    job.error_info = "Job concluded but sent no results."
                    logger.info(
                        f"Job {job_id} has concluded, but has not sent results after"
                        f" {constants.CONCLUDED_WITHOUT_RESULTS_GRACE_TIME_IN_SECS} seconds."
                        " Considering job failed."
                    )

            # We give the job some time to send its results and fail it otherwise.
            pyuv.Timer(self.event_loop).start(
                fail_job_if_still_no_results,
                constants.CONCLUDED_WITHOUT_RESULTS_GRACE_TIME_IN_SECS,
                repeat=0.0,  # No repeats
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

    def handle_unidentified_message(self, data, msg_type_idx, message):
        logger = logging.getLogger("cluster_utils")
        logger.error(
            f"Received a message I did not understand: {data}, {msg_type_idx},"
            f" {message}"
        )
