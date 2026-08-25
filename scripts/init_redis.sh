#!/bin/sh
nohup redis-server > redis.log 2>&1 &
until redis-cli ping | grep -q "PONG"; do
  echo "Aguardando o Redis iniciar..."
  sleep 1
done
echo "Redis está pronto!"
redis-cli CONFIG SET maxmemory 256mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET appendonly yes
redis-cli CONFIG SET appendfsync everysec