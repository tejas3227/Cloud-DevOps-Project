FROM nginx:alpine

COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;", "THIS_IS_INTENTIONALLY_BROKEN"]