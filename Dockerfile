ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache nginx gettext bash

COPY run.sh /run.sh
COPY nginx.conf.template /etc/nginx/nginx.conf.template

RUN chmod +x /run.sh

CMD ["/run.sh"]
