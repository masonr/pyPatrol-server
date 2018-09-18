import uuid;

class Job(object):
    """A job is a service check action that will be tasked to the multiple monitoring nodes

    Attributes:
        user_id: The user's ID that the job belongs to
        job_id: A UUID assigned to this job
        job_type: The type of job this service check is for (i.e. ping, cert, etc.)
        job_options: The arguments that will get passed to the montioring node to complete the service check
        completed: Whether or not the job is completed regardless of the result
        result: The result of the status check once completed
    """

    job_type = [ "status", "ping", "ping6", "http_response", "cert", "tcp_socket", "steam_server" ]

    def __init__(self, user_id, job_type, job_options):
        self.user_id = user_id
        self.job_id = uuid.uuid4().hex;
        self.job_type = job_type
        self.job_options = job_options
        self.completed = False
        self.result = None
