"""Functions for communicating with the cluster_utils server."""

from __future__ import annotations

import pickle
import socket
import sys
import traceback
from typing import Any

from cluster_utils.base.communication import MessageTypes

from . import submission_state


def send_message(message_type: MessageTypes, message: Any) -> None:
    """Send message to the cluster_utils server.

    Args:
        message_type: The message type.
        message: Additional information.  Needs to be pickleable.
    """
    msg_data = pickle.dumps((message_type, message))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet (IP)  # UDP
        # not sure if timeout is actually relevant for SOCK_DGRAM but let's set one to
        # be sure
        sock.settimeout(10)
        sock.sendto(
            msg_data,
            (
                submission_state.communication_server_ip,
                submission_state.communication_server_port,
            ),
        )
    except socket.error as e:
        print(
            f"ERROR: Failed to send message {message_type.name} to cluster_utils"
            f" server. | {e}",
            file=sys.stderr,
        )


def send_results_to_server(metrics):
    print(
        "Sending results to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.JOB_SENT_RESULTS, message=(submission_state.job_id, metrics)
    )


def report_exit_at_server():
    print(
        "Sending confirmation of exit to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(MessageTypes.JOB_CONCLUDED, message=(submission_state.job_id,))


def report_error_at_server(exctype, value, tb):
    print(
        "Sending errors to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.ERROR_ENCOUNTERED,
        message=(
            submission_state.job_id,
            traceback.format_exception(exctype, value, tb),
        ),
    )


def register_at_server(final_params):
    print(
        "Sending registration to: ",
        (
            submission_state.communication_server_ip,
            submission_state.communication_server_port,
        ),
    )
    send_message(
        MessageTypes.JOB_STARTED,
        message=(submission_state.job_id, socket.gethostname()),
    )
