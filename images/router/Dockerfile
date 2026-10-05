# Lab router: official FRRouting image + lab start script and configs.
# Build from the repository root:
#   docker build -f images/router/Dockerfile -t lab-router .
ARG FRR_TAG=10.0.0
FROM quay.io/frrouting/frr:${FRR_TAG}

# Full iproute2 is needed for VLAN subinterfaces; tcpdump for on-box captures.
RUN apk add --no-cache iproute2 tcpdump

COPY configs/RA /lab/configs/RA
COPY configs/RB /lab/configs/RB
COPY images/router/lab-router-start.sh /usr/local/bin/lab-router-start
COPY images/router/lab-evidence.sh /usr/local/bin/lab-evidence
RUN chmod +x /usr/local/bin/lab-router-start /usr/local/bin/lab-evidence

# The base image keeps ENTRYPOINT ["/sbin/tini", "--"].
CMD ["/usr/local/bin/lab-router-start"]
