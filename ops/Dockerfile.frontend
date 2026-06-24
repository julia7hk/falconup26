FROM node:22-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json* ./
RUN npm install

# Copy application code
COPY . .

RUN npm run build

CMD ["npm", "start", "--", "-p", "4040"]
