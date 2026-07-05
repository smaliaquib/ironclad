FROM grafana/grafana-oss:11.4.0

# Root, briefly, to install aws-cli (used by entrypoint.sh to fetch the admin
# password from SSM at container startup) and copy in provisioning config.
USER root
RUN apk add --no-cache aws-cli

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/ /var/lib/grafana/dashboards/
COPY entrypoint.sh /entrypoint.sh
# 472:472 - the official image's stable numeric grafana UID/GID convention,
# not a named user/group lookup (which failed here: "unknown user/group
# grafana:grafana" - apparently not present as a named passwd/group entry
# in this tag, even though 472 is documented as the grafana user's UID).
RUN chmod +x /entrypoint.sh && chown 472:472 /entrypoint.sh

USER 472
ENTRYPOINT ["/entrypoint.sh"]
