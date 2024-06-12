"""Global state module, storing information about the running job."""

communication_server_ip = None
communication_server_port = None
job_id = None
connection_details_available = False
connection_active = False
start_time: float
