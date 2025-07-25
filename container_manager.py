import atexit
import time
import json
import random
import string

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerNotRunningError
import docker
import paramiko.ssh_exception
import requests

from CTFd.models import db
from .models import ContainerInfoModel, ContainerFlagModel, ContainerFlagModel

teencode_dict = {
    'a': ['a', 'A', '4', '@'],
    'b': ['b', 'B', '|3'],
    'c': ['c', 'C', '('],
    'd': ['d', 'D'],
    'e': ['e', 'E', '3'],
    'f': ['f', 'F'],
    'g': ['g', 'G', '9'],
    'h': ['h', 'H', '#'],
    'i': ['i', 'I', '1', '|'],
    'j': ['j', 'J'],
    'k': ['k', 'K'],
    'l': ['l', 'L', '1', '|_'],
    'm': ['m', 'M'],
    'n': ['n', 'N'],
    'o': ['o', 'O', '0'],
    'p': ['p', 'P'],
    'q': ['q', 'Q'],
    'r': ['r', 'R'],
    's': ['s', 'S', '5', '$'],
    't': ['t', 'T', '7'],
    'u': ['u', 'U'],
    'v': ['v', 'V'],
    'w': ['w', 'W'],
    'x': ['x', 'X'],
    'y': ['y', 'Y'],
    'z': ['z', 'Z'],
    '_': ['_', '-'],
    '{': ['{'],
    '}': ['}'],
}

# Reverse mapping for teencode: maps each teencode variant to its base letter
reverse_teencode_dict = {}
for base, variants in teencode_dict.items():
    for v in variants:
        reverse_teencode_dict[v] = base


def generate_random_teencode(flag, how_many_teencode=8):
    # Robustly split flag into prefix, body, and suffix using first '{' and last '}'
    first_brace = flag.find('{')
    last_brace = flag.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        flag_prefix = flag[:first_brace+1]
        flag_body = flag[first_brace+1:last_brace]
        flag_suffix = flag[last_brace:]
    else:
        flag_prefix = ''
        flag_body = flag
        flag_suffix = ''

    indices = list(range(len(flag_body)))
    transform_indices = set(random.sample(indices, min(how_many_teencode, len(flag_body))))

    new_chars = []
    for i, char in enumerate(flag_body):
        base_char = reverse_teencode_dict.get(char, char)
        options = teencode_dict.get(base_char.lower(), [char])
        if i in transform_indices:
            filtered_options = [o for o in options if o != char]
            if filtered_options:
                new_chars.append(random.choice(filtered_options))
            else:
                new_chars.append(char)
        else:
            new_chars.append(char)
    return flag_prefix + ''.join(new_chars)


def generate_multiple_random_teencodes(flag, how_many_teencode=8, count=20):
    """Generate multiple teencode flags from a base flag."""
    return [generate_random_teencode(flag, how_many_teencode) for _ in range(count)]


def pregenerate_teencode_flags_for_challenge(challenge, base_flag, count=100, how_many_teencode=8):
    """
    Pre-generate a set of teencode flags for a challenge and store them in the database.
    Each flag is stored in ContainerFlagModel with only challenge_id and flag set.
    """
    from .models import ContainerFlagModel
    from CTFd.models import db

    teencode_flags = generate_multiple_random_teencodes(base_flag, how_many_teencode, count)
    for flag in teencode_flags:
        flag_entry = ContainerFlagModel(
            challenge_id=challenge.id,
            flag=flag
        )
        db.session.add(flag_entry)
    db.session.commit()
    return teencode_flags

def generate_random_flag(challenge):
    """Generate a random flag with the given length and format"""
    flag_length = challenge.random_flag_length
    random_part = "".join(
        random.choices(string.ascii_letters + string.digits, k=flag_length)
    )
    return f"{challenge.flag_prefix}{random_part}{challenge.flag_suffix}"


class ContainerException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self) -> str:
        if self.message:
            return self.message
        else:
            return "Unknown Container Exception"


def run_command(func):
    def wrapper_run_command(self, *args, **kwargs):
        # If client is not initialized, try to initialize it
        if self.client is None:
            try:
                self.initialize_connection(self.settings, self.app)
            except Exception as e:
                raise ContainerException("Docker is not connected: " + str(e))
        try:
            if self.client is None:
                raise ContainerException("Docker is not connected")
            if self.client.ping():
                return func(self, *args, **kwargs)
        except (
            paramiko.ssh_exception.SSHException,
            ConnectionError,
            requests.exceptions.ConnectionError,
        ) as e:
            # Try to reconnect before failing
            try:
                self.initialize_connection(self.settings, self.app)
            except Exception as e2:
                pass
            raise ContainerException(
                "Docker connection was lost. Please try your request again later."
            )

    return wrapper_run_command


class ContainerManager:
    def __init__(self, settings, app):
        self.settings = settings
        self.client = None
        self.app = app
        if (
            settings.get("docker_base_url") is None
            or settings.get("docker_base_url") == ""
        ):
            return

        # Connect to the docker daemon
        try:
            self.initialize_connection(settings, app)
        except ContainerException:
            print("Docker could not initialize or connect.")
            return

    def initialize_connection(self, settings, app) -> None:
        self.settings = settings
        self.app = app

        # Remove any leftover expiration schedulers
        try:
            self.expiration_scheduler.shutdown()
        except (SchedulerNotRunningError, AttributeError):
            # Scheduler was never running
            pass

        if settings.get("docker_base_url") is None:
            self.client = None
            return

        try:
            self.client = docker.DockerClient(base_url=settings.get("docker_base_url"))
        except docker.errors.DockerException as e:
            self.client = None
            raise ContainerException("CTFd could not connect to Docker")
        except TimeoutError as e:
            self.client = None
            raise ContainerException("CTFd timed out when connecting to Docker")
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            self.client = None
            raise ContainerException(
                "CTFd timed out when connecting to Docker: " + str(e)
            )
        except paramiko.ssh_exception.AuthenticationException as e:
            self.client = None
            raise ContainerException(
                "CTFd had an authentication error when connecting to Docker: " + str(e)
            )

        # Set up expiration scheduler
        try:
            self.expiration_seconds = int(settings.get("container_expiration", 0)) * 60
        except (ValueError, AttributeError):
            self.expiration_seconds = 0

        EXPIRATION_CHECK_INTERVAL = 5

        if self.expiration_seconds > 0:
            self.expiration_scheduler = BackgroundScheduler()
            self.expiration_scheduler.add_job(
                func=self.kill_expired_containers,
                # args=(app,),
                trigger="interval",
                seconds=EXPIRATION_CHECK_INTERVAL,
            )
            self.expiration_scheduler.start()

            # Shut down the scheduler when exiting the app
            atexit.register(lambda: self.expiration_scheduler.shutdown())

    @run_command
    def kill_expired_containers(self):
        with self.app.app_context():
            containers: "list[ContainerInfoModel]" = ContainerInfoModel.query.all()

            for container in containers:
                delta_seconds = container.expires - int(time.time())
                if delta_seconds < 0:
                    try:
                        self.kill_container(container.container_id)
                    except ContainerException:
                        print(
                            "[Container Expiry Job] Docker is not initialized. Please check your settings."
                        )

                    db.session.delete(container)
                    db.session.commit()

    @run_command
    def is_container_running(self, container_id: str) -> bool:
        container = self.client.containers.list(filters={"id": container_id})
        if len(container) == 0:
            return False
        return container[0].status == "running"

    @run_command
    def create_container(self, challenge, xid, is_team):
        from .models import ContainerFlagModel
        from CTFd.models import db
        import random

        kwargs = {}

        teencode_flag_entry = (
            ContainerFlagModel.query
            .filter_by(challenge_id=challenge.id, container_id=None, used=False)
            .order_by(db.func.random())
            .first()
        )
        if teencode_flag_entry:
            flag = teencode_flag_entry.flag
        else:
            flag = (
                generate_random_flag(challenge)
                if challenge.flag_mode == "random"
                else challenge.flag_prefix + challenge.flag_suffix
            )
            teencode_flag_entry = None

        if self.settings.get("container_maxmemory"):
            try:
                mem_limit = int(self.settings.get("container_maxmemory"))
                if mem_limit > 0:
                    kwargs["mem_limit"] = f"{mem_limit}m"
            except ValueError:
                ContainerException(
                    "Configured container memory limit must be an integer"
                )
        if self.settings.get("container_maxcpu"):
            try:
                cpu_period = float(self.settings.get("container_maxcpu"))
                if cpu_period > 0:
                    kwargs["cpu_quota"] = int(cpu_period * 100000)
                    kwargs["cpu_period"] = 100000
            except ValueError:
                ContainerException("Configured container CPU limit must be a number")

        volumes = challenge.volumes
        if volumes is not None and volumes != "":
            print("Volumes:", volumes)
            try:
                volumes_dict = json.loads(volumes)
                kwargs["volumes"] = volumes_dict
            except json.decoder.JSONDecodeError:
                raise ContainerException("Volumes JSON string is invalid")

        try:
            container = self.client.containers.run(
                challenge.image,
                ports={str(challenge.port): None},
                command=challenge.command,
                detach=True,
                auto_remove=True,
                environment={"FLAG": flag},
                **kwargs,
            )
            port = self.get_container_port(container.id)
            if port is None:
                raise ContainerException("Could not get container port")
            expires = int(time.time() + self.expiration_seconds)

            new_container_entry = ContainerInfoModel(
                container_id=container.id,
                challenge_id=challenge.id,
                team_id=xid if is_team else None,
                user_id=None if is_team else xid,
                port=port,
                flag=flag,
                timestamp=int(time.time()),
                expires=expires,
            )
            db.session.add(new_container_entry)
            db.session.commit()

            # Assign the flag entry to this container and user/team
            if teencode_flag_entry:
                teencode_flag_entry.container_id = container.id
                teencode_flag_entry.team_id = xid if is_team else None
                teencode_flag_entry.user_id = None if is_team else xid
                db.session.commit()
            else:
                # Save the fallback flag in the database
                new_flag_entry = ContainerFlagModel(
                    challenge_id=challenge.id,
                    container_id=container.id,
                    flag=flag,
                    team_id=xid if is_team else None,
                    user_id=None if is_team else xid,
                )
                db.session.add(new_flag_entry)
                db.session.commit()

            return {"container": container, "expires": expires, "port": port}
        except docker.errors.ImageNotFound:
            raise ContainerException("Docker image not found")

    @run_command
    def get_container_port(self, container_id: str) -> "str|None":
        max_retries = 10
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                container = self.client.containers.get(container_id)
                
                # Wait for container to be running
                if container.status != "running":
                    print(f"[DEBUG] Container {container_id} status: {container.status} (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:  # Don't sleep on last attempt
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"[DEBUG] Container {container_id} failed to start after {max_retries} attempts")
                        return None
                
                # Check if ports are available
                if not container.ports:
                    print(f"[DEBUG] Container {container_id} has no ports yet (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:  # Don't sleep on last attempt
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"[DEBUG] Container {container_id} ports never became available after {max_retries} attempts")
                        return None
                
                # Get the host port
                for port in list(container.ports.values()):
                    if port is not None and len(port) > 0:
                        host_port = port[0]["HostPort"]
                        print(f"[DEBUG] Container {container_id} got port: {host_port}")
                        return host_port
                
                # If we get here, no ports were found
                print(f"[DEBUG] Container {container_id} has ports but none are valid (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:  # Don't sleep on last attempt
                    time.sleep(retry_delay)
                    continue
                else:
                    return None
                    
            except (KeyError, IndexError, docker.errors.NotFound) as e:
                print(f"[DEBUG] Container {container_id} error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:  # Don't sleep on last attempt
                    time.sleep(retry_delay)
                    continue
                else:
                    return None
        
        return None
        
    @run_command
    def get_images(self) -> "list[str]|None":
        try:
            images = self.client.images.list()
        except (KeyError, IndexError):
            return []

        images_list = []
        for image in images:
            if len(image.tags) > 0:
                images_list.append(image.tags[0])

        images_list.sort()
        return images_list

    @run_command
    def kill_container(self, container_id: str):
        try:
            self.client.containers.get(container_id).kill()

            container_info = ContainerInfoModel.query.filter_by(
                container_id=container_id
            ).first()
            if not container_info:
                return  # No matching record => nothing else to do

            challenge = container_info.challenge

            used_flags = ContainerFlagModel.query.filter_by(
                container_id=container_id
            ).all()

            if challenge.flag_mode == "static":
                # Remove all flags for static-mode challenges (ignore used or not used)
                for f in used_flags:
                    db.session.delete(f)
            else:
                for f in used_flags:
                    # Reset flag assignment so it can be reused
                    f.container_id = None
                    f.team_id = None
                    f.user_id = None
                    if not f.used:
                        f.used = False
            db.session.commit()

        except docker.errors.NotFound:
            pass

    def is_connected(self) -> bool:
        try:
            self.client.ping()
        except:
            return False
        return True
