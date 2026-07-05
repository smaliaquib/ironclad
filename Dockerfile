FROM grafana/grafana-oss:11.4.0

# Root, briefly, to install aws-cli (used by entrypoint.sh to fetch the admin
# password from SSM at container startup) and copy in provisioning config.
USER root
RUN apk add --no-cache aws-cli

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/ /var/lib/grafana/dashboards/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown grafana:grafana /entrypoint.sh

USER grafana
ENTRYPOINT ["/entrypoint.sh"]
