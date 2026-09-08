# Two-stage frontend image: build assets with Node, then serve dist with Nginx.
# VITE_* values are public build-time settings; changing them requires a rebuild.
FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_WS_BASE_URL=
ARG VITE_USE_MOCKS=false
ARG VITE_MOCK_DELAY_MS=800

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_WS_BASE_URL=$VITE_WS_BASE_URL \
    VITE_USE_MOCKS=$VITE_USE_MOCKS \
    VITE_MOCK_DELAY_MS=$VITE_MOCK_DELAY_MS

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
