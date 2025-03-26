FROM nginx:latest

COPY main.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf
RUN apt-get update && apt-get install -y iproute2