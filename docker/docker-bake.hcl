group "default" {
  targets = ["redis", "redisinsight", "tests", "docs", "sandbox", "backend-dev", "frontend"]
}

group "app" {
  targets = ["redis", "backend", "frontend"]
}

group "infra" {
  targets = ["redis", "redisinsight"]
}

group "ci-checks" {
  targets = ["tests", "docs"]
}

group "backend" {
  targets = ["backend-dev", "backend-test", "backend-prod"]
}

group "frontend" {
  targets = ["frontend-dev", "frontend-test", "frontend-prod"]
}

target "redis" {
  context    = "."
  dockerfile = "docker/Dockerfile.redis"
  tags       = ["health-redis:ci"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=redis"]
  cache-to   = ["type=gha,scope=redis,mode=max"]
}

target "redisinsight" {
  context    = "."
  dockerfile = "docker/Dockerfile.redisinsight"
  tags       = ["health-redisinsight:ci"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=redisinsight"]
  cache-to   = ["type=gha,scope=redisinsight,mode=max"]
}

target "tests" {
  context    = "."
  dockerfile = "docker/Dockerfile.tests"
  tags       = ["health-test-runner:ci"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=tests"]
  cache-to   = ["type=gha,scope=tests,mode=max"]
}

target "docs" {
  context    = "."
  dockerfile = "docker/Dockerfile.docs"
  tags       = ["health-docs:ci"]
  output     = ["type=docker"]
  cache-from = ["type=gha,scope=docs"]
  cache-to   = ["type=gha,scope=docs,mode=max"]
}

target "sandbox" {
  context    = "."
  dockerfile = "docker/Dockerfile.sandbox"
  tags       = ["health-sandbox:ci"]
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
