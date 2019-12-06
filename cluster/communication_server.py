import socket
import pyuv
import signal
import pickle
import threading

msg_types = {0: 'job_started',
             1: 'error_encountered',
             2: 'job_concluded'}

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
    return self.ip_adress, self.port

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
        if msg_types[msg_type_idx] == 'job_started':
          self.handle_job_started(message)
        elif msg_types[msg_type_idx] == 'error_encountered':
          self.handle_error_encountered(message)
        elif msg_types[msg_type_idx] == 'job_concluded':
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
    job.status = 0
    #self.jobs.append(MinJob(job_id, settings, 0))


  def handle_error_encountered(self, message):
    raise NotImplementedError()
    job_id, exctype, value, tb = message
    job = self.get_job(job_id)
    if job is None:
      raise ValueError('Job was not in the list of jobs but encountered an error... fucked up twice, huh?')
    job.status = 1
    job.error_info = exctype, value, tb


  def handle_job_concluded(self, message):
    job_id, metrics = message
    job = self.cluster_system.get_job(job_id)
    if job is None:
      raise ValueError('Received a end-message from a job that is not listed in the cluster interface system')
    #self.cluster_system.set_metrics(job_id, metrics)
    job.metrics = metrics
    job.set_results()
    job.status = 2
    if job.get_results(False) is None:
      raise ValueError('Job concluded without submitting metrics')



  def handle_unidentified_message(self, data, msg_type_idx, message):
    print("Received a message I did not understand:")
    print(data)
    print(msg_type_idx, type(msg_type_idx))
    print(msg_types[msg_type_idx], type(msg_types[msg_type_idx]))
    print(message, type(message))

  '''
  @property
  def running_jobs(self):
    return [job for job in self.jobs if job.status == 0]

  @property
  def n_running_jobs(self):
      return len(self.running_jobs)

  @property
  def concluded_jobs(self):
    return [job for job in self.jobs if job.status == 2]

  @property
  def n_concluded_jobs(self):
    return len(self.concluded_jobs)

  @property
  def failed_jobs(self):
    return [job for job in self.jobs if job.status == 1]

  @property
  def n_failed_jobs(self):
    return len(self.failed_jobs)

  def __repr__(self):
    return ('Communication Server Information \n'
            'Running: {.n_running_jobs}, Failed: {.n_failed_jobs}, Completed: {.n_concluded_jobs}').format(*(3 * [self]))

  '''