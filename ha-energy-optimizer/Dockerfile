ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN echo '#!/bin/sh' > /run.sh \
 && echo 'echo "Hello from HA Energy Optimizer"' >> /run.sh \
 && echo 'while true; do sleep 30; done' >> /run.sh \
 && chmod 755 /run.sh

CMD ["/run.sh"]
