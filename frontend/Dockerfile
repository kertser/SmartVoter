FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# standalone output requires static assets to be copied manually
RUN cp -r .next/static .next/standalone/.next/static 2>/dev/null || true && \
    cp -r public .next/standalone/public 2>/dev/null || true

EXPOSE 3000
# Must use standalone server directly — "next start" does not work with output:standalone
CMD ["node", ".next/standalone/server.js"]
