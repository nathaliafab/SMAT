# Running SMAT with Docker Compose

This guide explains how to run SMAT in a containerized environment using **Docker Compose**. This ensures a consistent environment with Python 3.11, Java 8, and Maven, regardless of your host operating system.

## 1. Prerequisites

Install Docker on your system:

* **Docker Desktop** (Recommended for Windows and Mac): [Download here](https://docs.docker.com/desktop/)
* **Docker Engine** (For Linux): [Installation Guide](https://docs.docker.com/engine/install/)

---

## 2. Configuration

Before running the container, you need to configure three files to ensure the paths match the Docker environment.

### A. Docker Compose (Dataset Path)

Open `docker-compose.yml` and point the dataset volume to your local path:

```yaml
volumes:
  - .:/app
  # Replace the path below with the path to your dataset on your host machine
  - /path/to/your/mergedataset/:/data/dataset:ro

```

*Note: The `:ro` flag ensures your dataset is read-only for safety.*

### B. SMAT Input Config (`input-smat.json`)

The `input-smat.json` should be in the **root directory** of the project, so that the container can see it. Internally, the scenario jars must point to the `/data/dataset/` path, for example:

```json
{
  ...
  "scenarioJars": {
      "base": "/data/dataset/antlr4/69ff2669eec265e25721dbc27cb00f6c381d0b41/...",
      ...
    },
  ...
}
```

### C. Environment Config (`nimrod/tests/env-config.json`)

Point the `input_smat` path to the location inside the container. If it is on the root folder:

```json
"input_path": "/app/input-smat.json",
```

---

## 3. Running the Container

Navigate to the project root and run the following command according to your OS:

### Linux & macOS (Terminal)

The following command passes your user and group IDs to avoid permission issues with generated files:

```bash
USER_ID=$(id -u) GROUP_ID=$(id -g) docker compose run --rm --build smat
```

### Windows (PowerShell)

In PowerShell, the variables are handled differently:

```powershell
$env:USER_ID=1000; $env:GROUP_ID=1000; docker compose run --rm --build smat
```

*Note: On Windows, the default UID/GID 1000 is usually sufficient for Docker Desktop.*

---

## 4. Usage Inside the Container

Once the command finishes, you will be inside the Ubuntu shell at `/app`. You can run tests or start an analysis:

```bash
# Check if the dataset is visible
ls /data/dataset

# Run SMAT analysis
python3 -m nimrod

# Run tests
pytest -k 'not test_general_behavior_study_semantic_conflict'
```

### Command Breakdown:

* `run`: Starts a one-off container for interactive use.
* `--rm`: Automatically removes the container upon exit to keep your system clean.
* `--build`: Forces a rebuild of the image if you modified the Dockerfile or requirements.
* `smat`: The service name defined in `docker-compose.yml`.

---

## Troubleshooting

* **Dataset Not Found**: Ensure the path on the left side of the colon in `docker-compose.yml` is an absolute path to your local folder.
* **Permission Denied**: On Linux, double-check that `USER_ID` and `GROUP_ID` match the output of the `id` command on your host terminal.
* **File Changes**: Since we use volumes, any code change made on your host machine will be instantly reflected inside the container.
