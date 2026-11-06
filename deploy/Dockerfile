# The image builds the site from source rather than copying a prebuilt directory,
# so a deployed page can never contain a claim that failed verification:
# tool/render.py runs the validator first and exits non-zero if any citation is
# unresolvable. Failing here fails the build, which is the point.
FROM python:3.12-alpine AS builder

WORKDIR /site
RUN pip install --no-cache-dir pyyaml

COPY tool/ tool/
COPY cases/ cases/
COPY evidence/ evidence/
COPY catalog/ catalog/
COPY schema/ schema/

RUN python tool/render.py

FROM nginx:1.29-alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /site/build /usr/share/nginx/html

EXPOSE 8080
