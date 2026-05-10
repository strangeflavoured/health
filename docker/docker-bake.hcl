group "default" {
  targets = ["infra", "dev", "tests", "docs", "sandbox"]
}

group "dev" {
  targets = ["backend-dev", "frontend-dev"]
}

group "prod" {
  targets = ["backend-prod", "frontend-prod"]
}

group "infra" {
  targets = ["redis-init", "redis", "redisinsight"]
}

group "tests" {
  targets = ["src-test", "backend-test", "frontend-test"]
}

group "backend" {
  targets = ["backend-dev", "backend-test", "backend-prod"]
}

group "frontend" {
  targets = ["frontend-dev", "frontend-test", "frontend-prod"]
}

target "redis-init" {
  context    = "."
  dockerfile = "docker/Dockerfile.redis-init"
  tags       = ["health-redis-init"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=redis-init"]
  cache-to   = ["type=gha,scope=redis-init,mode=max"]
}

target "redis" {
  context    = "."
  dockerfile = "docker/Dockerfile.redis"
  tags       = ["health-redis"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=redis"]
  cache-to   = ["type=gha,scope=redis,mode=max"]
}

target "redisinsight" {
  context    = "."
  dockerfile = "docker/Dockerfile.redisinsight"
  tags       = ["health-redisinsight"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=redisinsight"]
  cache-to   = ["type=gha,scope=redisinsight,mode=max"]
}

target "src-test" {
  context    = "."
  dockerfile = "docker/Dockerfile.tests"
  tags       = ["health-test-runner"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=tests"]
  cache-to   = ["type=gha,scope=tests,mode=max"]
}

target "docs" {
  context    = "."
  dockerfile = "docker/Dockerfile.docs"
  tags       = ["health-docs"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=docs"]
  cache-to   = ["type=gha,scope=docs,mode=max"]
}

target "sandbox" {
  context    = "."
  dockerfile = "docker/Dockerfile.sandbox"
  tags       = ["health-sandbox"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=sandbox"]
  cache-to   = ["type=gha,scope=sandbox,mode=max"]
}

target "backend-dev" {
  context    = "."
  dockerfile = "docker/Dockerfile.backend"
  target     = "dev"
  tags       = ["health-backend:dev"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=backend"]
  cache-to   = ["type=gha,scope=backend,mode=max"]
}

target "backend-test" {
  context    = "."
  dockerfile = "docker/Dockerfile.backend"
  target     = "test"
  tags       = ["health-backend:test"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=backend"]
  cache-to   = ["type=gha,scope=backend,mode=max"]
}

target "backend-prod" {
  context    = "."
  dockerfile = "docker/Dockerfile.backend"
  target     = "prod"
  tags       = ["health-backend:prod"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=backend"]
  cache-to   = ["type=gha,scope=backend,mode=max"]
}

target "frontend-dev" {
  context    = "."
  dockerfile = "docker/Dockerfile.frontend"
  target     = "dev"
  tags       = ["health-frontend:dev"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=frontend"]
  cache-to   = ["type=gha,scope=frontend,mode=max"]
}

target "frontend-test" {
  context    = "."
  dockerfile = "docker/Dockerfile.frontend"
  target     = "test"
  tags       = ["health-frontend:test"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=frontend"]
  cache-to   = ["type=gha,scope=frontend,mode=max"]
}

target "frontend-prod" {
  context    = "."
  dockerfile = "docker/Dockerfile.frontend"
  target     = "prod"
  tags       = ["health-frontend:prod"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=frontend"]
  cache-to   = ["type=gha,scope=frontend,mode=max"]
}
