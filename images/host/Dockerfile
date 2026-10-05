# Lab host: small Linux end host with test tools.
# Build from the repository root:
#   docker build -f images/host/Dockerfile -t lab-host .
FROM alpine:3.20

# iputils: ping with -D timestamps (BusyBox ping lacks it)
RUN apk add --no-cache iputils iproute2 iperf3 tcpdump python3

COPY tools/failover_probe.py /usr/local/bin/failover-probe
RUN chmod +x /usr/local/bin/failover-probe

CMD ["/bin/sh"]
