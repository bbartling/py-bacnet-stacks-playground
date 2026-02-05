# Day 40 – Containerising Your Scraper with Docker

## Goal

Learn how to package your CSV‑scraping script into a Docker container and
deploy it with a restart policy so that it automatically recovers from
crashes and survives host reboots.  By the end of this lesson you
will be able to write a simple `Dockerfile`, build an image, run it
with the `--restart` flag and use a `docker‑compose.yml` file to
configure persistent volumes and restart policies.

## Concept

Containerisation makes it easy to run your Python scraper on any
platform.  When you run a container you can tell Docker what to do
when the process exits by supplying a **restart policy**.  The
official Docker documentation lists several options for the
`--restart` flag: `no` (don’t automatically restart),
`on‑failure[:max-retries]` (restart on error), `always` (restart the
container if it stops) and `unless‑stopped`.  Using
`always` or `unless‑stopped` ensures that your scraper restarts after
a crash or after the Docker daemon restarts.  You
should not combine Docker restart policies with host‑level process
managers like systemd to avoid conflicts.

## How to Use It

1. **Prepare your script** – Place the same `csv_scraper.py` from
   Day 39 into a new directory.  This script will be the entry point of
   your Docker image.

2. **Write a Dockerfile** – Create a file named `Dockerfile` with the
   following content:

   ```Dockerfile
   # Use the official Python image as a base
   FROM python:3.11-slim

   # Create a working directory in the container
   WORKDIR /app

   # Copy your scraping script into the container
   COPY csv_scraper.py .

   # Install any dependencies here (e.g. bacpypes3, pandas)
   RUN pip install --no-cache-dir bacpypes3 pandas

   # Run the script when the container starts
   CMD ["python", "csv_scraper.py"]
   ```

   This image starts from a minimal Python base, copies your script,
   installs dependencies and runs the scraper.  When the container
   exits, Docker uses the restart policy to decide what to do.

3. **Build the image** – In the directory containing your
   `Dockerfile` and script, run:

   ```bash
   docker build -t csv-scraper:latest .
   ```

   This command creates a local image tagged `csv-scraper:latest`.

4. **Run with a restart policy** – Start the container with a restart
   policy and mount a host directory to store CSV data:

   ```bash
   mkdir -p ~/data
   docker run -d --name csv-scraper \
     --restart unless-stopped \
     -v ~/data:/app/data \
     csv-scraper:latest
   ```

   The `--restart unless-stopped` option tells Docker to restart the
   container if it stops, except when you explicitly stop it.
   Using a volume (`-v`) maps the container’s `/app/data` directory to
   `~/data` on the host so your CSV logs persist.  You can inspect
   running containers with `docker ps` and view logs with
   `docker logs csv-scraper`.

5. **Use docker‑compose** – For more complex setups, create a
   `docker-compose.yml` file:

   ```yaml
   version: '3'
   services:
     scraper:
       build: .
       container_name: csv-scraper
       restart: unless-stopped
       volumes:
         - ./data:/app/data
   ```

   Then start the service in detached mode:

   ```bash
   docker compose up -d
   ```

   Docker Compose automatically applies the `restart: unless-stopped`
   policy to the `scraper` service.  The container restarts on failure
   and after host reboots but stays stopped if you manually stop it.

6. **Manage the container** – Use `docker stop csv-scraper` to stop
   the container.  When using `unless-stopped`, it will not restart
   until the host reboots or you run `docker start csv-scraper`.  To
   change the restart policy for an existing container, use
   `docker update --restart always csv-scraper`.

## Why This Matters

Containers provide an easy way to deploy the same scraping code on any
host without worrying about dependencies.  Docker’s restart policies
allow your application to recover from failures automatically,
making it suitable for unattended operation in industrial and
building‑automation environments.  Using Compose you can describe
multiple services (e.g. a scraper, a database and a web UI) in a
single file and ensure they all start with the correct policies.

## Mini Examples

* Build and run the example container, then kill it with `docker kill
  csv-scraper`.  It should restart automatically thanks to the
  `unless-stopped` policy.
* Change the restart policy to `on-failure:5` and observe how the
  container stops after exceeding the maximum number of retries.
* Use `docker-compose logs -f scraper` to watch the CSV file being
  written in real time.

## Micro Exercises

1. Modify the `Dockerfile` to install additional packages (e.g.,
   `hvac` for BACnet communications) and rebuild the image.
2. Create a second service in `docker-compose.yml` that tails the CSV
   file using `tail -f` and restart it with the `always` policy.
3. Inspect the restart policy of a running container using
   `docker inspect -f '{{ .HostConfig.RestartPolicy.Name }}' csv-scraper`.
4. Research the difference between `restart: always` and
   `restart: unless-stopped` and choose which is more appropriate for a
   production deployment.

## Key Takeaway

Docker’s `--restart` flag and Compose’s `restart` option let you
deploy your Python scraper as a self‑healing service.  The
`always` and `unless-stopped` policies cause the container to restart
after crashes and host reboots, providing
production‑ready reliability without relying on host‑level process
managers.