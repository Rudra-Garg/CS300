FROM nginx:latest

COPY main.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/nginx.conf
RUN apt-get update && apt-get install -y iproute2