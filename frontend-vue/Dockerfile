FROM node:24-alpine AS dependencies
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:24-alpine AS dev
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
CMD ["npm", "run", "dev"]

FROM node:24-alpine AS build
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
