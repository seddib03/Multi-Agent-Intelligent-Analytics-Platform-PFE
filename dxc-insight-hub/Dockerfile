FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

EXPOSE 5173

# Run Vite dev server for docker-compose_dev environment
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
