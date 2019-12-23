import socket
import pyuv
import signal
import pickle
import threading
from warnings import warn

from .job import JobStatus


class MessageTypes():
  JOB_STARTED = 0
  ERROR_ENCOUNTERED = 1
  JOB_SENT_RESULTS = 2
  JOB_CONCLUDED = 3

class MinJob():
  def __init__(self, id, settings, status):
    self.id =  id
    self.settings = settings
    self.status = status
    self.metrics = None

class CommunicationServer():

  def __init__(self, cluster_system):
    self.ip_adress = self.get_own_ip()
    self.port = None
    print("Running on IP: ", self.ip_adress)
    self.start_listening()
    self.cluster_system = cluster_system

  @property
  def connection_info(self):
    if self.ip_adress is None or self.port is None:
      raise ValueError('Either IP adress or port are not known yet.')
    return {'ip': self.ip_adress, 'port': self.port}

  def get_own_ip(self):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
      # doesn't even have to be reachable
      s.connect(('10.255.255.255', 1))
      IP = s.getsockname()[0]
    except:
      IP = '127.0.0.1'
    finally:
      s.close()
    return IP

  def start_listening(self):
    def on_read(handle, ip_port, flags, data, error):
      if data is not None:
        #handle.send(ip_port, data) This would be a way to ensure messaging worked well
        msg_type_idx, message = pickle.loads(data)
        if msg_type_idx == MessageTypes.JOB_STARTED:
          self.handle_job_started(message)
        elif msg_type_idx == MessageTypes.ERROR_ENCOUNTERED:
          self.handle_error_encountered(message)
        elif msg_type_idx == MessageTypes.JOB_SENT_RESULTS:
          self.handle_job_sent_results(message)
        elif msg_type_idx == MessageTypes.JOB_CONCLUDED:
          self.handle_job_concluded(message)
        else:
          self.handle_unidentified_message(data, msg_type_idx, message)

    def async_exit(async):
      async.close()
      signal_h.close()
      server.close()

    def signal_cb(sig, frame):
      async.send(async_exit)

    loop = pyuv.Loop.default_loop()
    async = pyuv.Async(loop)

    server = pyuv.UDP(loop)
    server.bind((self.ip_adress, 0))
    self.port = server.getsockname()[1]
    print("Running on Port: ", self.port)
    server.start_recv(on_read)

    signal_h = pyuv.Signal(loop)
    signal_h.start(signal_cb, signal.SIGINT)

    t = threading.Thread(target=loop.run, daemon=True)
    t.start()

    signal.signal(signal.SIGINT, signal_cb)


  def handle_job_started(self, message):
    job_id, = message
    job = self.cluster_system.get_job(job_id)
    if job is None:
      raise ValueError('Received a start-message from a job that is not listed in the cluster interface system')
    job.status = JobStatus.RUNNING
    #self.jobs.append(MinJob(job_id, settings, 0))


  def handle_error_encountered(self, message):
    job_id, strings = message
    job = self.cluster_system.get_job(job_id)
    if job is None:
      raise ValueError('Job was not in the list of jobs but encountered an error... fucked up twice, huh?')
    job.status = JobStatus.FAILED
    job.error_info = ''.join(strings)


  def handle_job_sent_results(self, message):
    job_id, metrics = message
    job = self.cluster_system.get_job(job_id)
    if job is None:
      raise ValueError('Received a results-message from a job that is not listed in the cluster interface system')
    job.metrics = metrics
    job.set_results()
    job.status = JobStatus.SENT_RESULTS
    if job.get_results() is None:
      raise ValueError('Job sent metrics but something went wrong')

  def handle_job_concluded(self, message):
    job_id, = message
    job = self.cluster_system.get_job(job_id)
    if job is None:
      raise ValueError('Received a job-concluded-message from a job that is not listed in the cluster interface system')
    if not job.status == JobStatus.SENT_RESULTS or job.get_results() is None:
      job.status = JobStatus.FAILED
      warn('Job concluded without submitting metrics or metrics where not received properly')
    job.status = JobStatus.CONCLUDED

  def handle_unidentified_message(self, data, msg_type_idx, message):
    print("Received a message I did not understand:")
    print(data)
    print(msg_type_idx, type(msg_type_idx))
    print(message, type(message))
