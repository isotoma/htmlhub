FROM python:2-alpine AS build
RUN apk add --no-cache build-base libffi-dev openssl-dev

COPY requirements.txt /app/
WORKDIR /app
COPY htmlhub /app/htmlhub
COPY setup.py /app/
COPY README.rst /app/
COPY CHANGES /app/
RUN pip install -r requirements.txt -e .

FROM python:2-alpine
RUN apk add --no-cache libffi openssl
WORKDIR /app
COPY --from=build /app /app
COPY --from=build /usr/local /usr/local
ENV GITHUB_USERNAME htmlhub
ENV GITHUB_PASSWORD secret
ENV CACHE_EXPIRY 30
ENV PORT 80
CMD htmlhub