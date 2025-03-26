FROM nginx
COPY main.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN apt-get update && apt-get install -y iproute2