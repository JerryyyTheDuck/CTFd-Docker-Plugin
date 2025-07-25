# CTFd Containers Plugin

<div align="center">
  <h3 align="center">CTFd Containers Plugin</h3>
  <p align="center">
    A plugin for CTFd to create secure, containerized challenges with advanced per-instance flag management and anti-cheat features.
  </p>
</div>

## Features

- **Per-Instance Teencode Flags:**
  - This feature is inspired by GPNCTF
  - When an admin creates a challenge, a pool of unique teencode-style flags is pre-generated and stored in the database.
  - When a user/team creates a container instance, a random unused flag from the pool is assigned to them.
  - Flags are generated using a customizable teencode mapping, supporting diverse and obfuscated flag variants.

- **Anti-Cheat Detection:**
  - If a user/team submits a flag assigned to another user/team, the system detects cheating and logs the incident.
  - Flags can only be used by the user/team they are assigned to, and only once.
  - Cheating attempts can trigger bans or notifications as configured.

- **Automatic Flag Reuse Prevention:**
  - When a user/team terminates an instance, the flag assignment is reset, allowing the flag to be reassigned if unused.
  - Flags are never reused across users/teams unless explicitly allowed by the admin.

- **Admin & User Workflows:**
  - Admins can create challenges with a single flag input (no suffix needed).
  - Flags are automatically teencode-variant generated and managed.
  - Users get a unique flag per instance, and cannot share or reuse flags.

- **Container Management:**
  - Supports both local and remote Docker daemons (via SSH).
  - Admin dashboard for monitoring and managing running containers.
  - Per-challenge and per-user/team container tracking.

- **UI Improvements:**
  - Clean challenge creation/update forms (no flag suffix field).
  - Real-time feedback for flag submission and cheating detection.

## Getting Started

### Prerequisites
- CTFd instance (Docker or direct)
- Docker (local or remote)
- (Optional) SSH access for remote Docker

### Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/JerryyyTheDuck/CTFd-Docker-Plugin.git
   ```
2. Move the folder to the CTFd plugins directory:
   ```bash
   mv CTFd-Docker-Plugin containers
   mv containers /path/to/CTFd/plugins/
   ```

### Usage
- Go to the plugin settings page: `/containers/settings`
- Create a new challenge. Enter your flag in the "Flag" field (no suffix needed).
- The system will automatically generate a pool of teencode flags for the challenge.
- When users create an instance, they are assigned a unique flag from the pool.
- If a user submits a flag not assigned to them, or reuses a flag, cheating is detected and logged.

### Using Local Docker Daemon

#### Case A: **CTFd Running Directly on Host:**
  - Go to the plugin settings page: `/containers/settings`
  - Fill in all fields except the `Base URL`.

 ![image](https://hackmd.io/_uploads/rkwpKrbPel.png)


#### Case B: **CTFd Running via Docker:**
  - Map the Docker socket into the CTFd container by modify the `docker-compose.yml` file:
  ```bash
  services:
    ctfd:
      ...
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock
      ...
  ```
  - Restart CTFd
  - Go to the plugin settings page: `/containers/settings`
  - Fill in all fields except the `Base URL`.

### Using Remote Docker via SSH

For remote Docker, the CTFd host must have SSH access to the remote server.

#### Prerequisites:
- **SSH access** from the CTFd host to the Docker server
- The remote server's fingerprint should be in the `known_hosts` file
- SSH key files (`id_rsa`) and an SSH config file should be available

#### Case A: **CTFd Running via Docker**

1. **Prepare SSH Config:**
   ```bash
   mkdir ssh_config
   cp ~/.ssh/id_rsa ~/.ssh/known_hosts ~/.ssh/config ssh_config/
   ```

2. **Mount SSH Config into the CTFd container:**
   ```yaml
   services:
     ctfd:
       ...
       volumes:
         - ./ssh_config:/root/.ssh:ro
       ...
   ```

3. **Restart CTFd:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

#### Case B: **CTFd Running Directly on Host**

1. **Ensure SSH Access:**
   - Test the connection:
     ```bash
     ssh user@remote-server
     ```

2. **Configure Docker Base URL:**
   - In the CTFd plugin settings page (`/containers/settings`), set:
     ```
     Base URL: ssh://user@remote-server
     ```

3. **Restart CTFd:**
   ```bash
   sudo systemctl restart ctfd
   ```



## Demo

### Admin Dashboard
- Manage running containers

![image](https://hackmd.io/_uploads/Hyg-9BbPxg.png)

- Monitor flag assignments and cheating attempts

![image](https://hackmd.io/_uploads/HJWQiS-wgg.png)



### Challenge View
- Users receive a unique teencode flag per instance

![image](https://hackmd.io/_uploads/r1mP5SWPex.png)

- User can spawn and extend the instance if they want

![image](https://hackmd.io/_uploads/rJcaiSWPgx.png)

- Cheating attempts are detected and handled automatically. If user are detected as cheating, their POV will be below

![image](https://hackmd.io/_uploads/HkDa5Hbwxe.png)

![image](https://hackmd.io/_uploads/HkrCcSZvge.png)

### Fame or shame notification

![image](https://hackmd.io/_uploads/B1GZjBbPgx.png)

## Roadmap
- [x] Per-instance teencode flag assignment
- [x] Anti-cheat detection and logging
- [x] Admin dashboard for container and flag management
- [x] Clean UI for challenge creation/update
- [x] Support for both user and team modes
- [x] Fame or shame announcement

## License
Distributed under the MIT License. See `LICENSE.txt` for details.

> This plugin is an upgrade of [andyjsmith's plugin](https://github.com/andyjsmith/CTFd-Docker-Plugin) with additional features from [phannhat17](https://github.com/phannhat17/CTFd-Docker-Plugin) and major improvements for secure, per-instance flag management.

