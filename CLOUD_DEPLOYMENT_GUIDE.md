# Smart Order Router - Cloud Deployment Guide

This guide will help you deploy your Smart Order Router application to various cloud platforms.

## 🚀 Quick Start

### Prerequisites

- Docker installed on your local machine
- Cloud platform account (AWS, Heroku, Google Cloud, or Azure)
- Exchange API keys for trading

### 1. Local Testing with Docker

First, test your application locally using Docker Compose:

```bash
# Clone and navigate to your project
cd smart-order-router

# Create environment file
cp .env.example .env
# Edit .env with your exchange API keys

# Start the application
docker-compose up --build

# Access the application
# API: http://localhost:8000
# UI: http://localhost:8501
# Docs: http://localhost:8000/docs
```

## ☁️ Cloud Deployment Options

### Option 1: AWS (Recommended for Production)

AWS provides the most robust and scalable infrastructure for production deployments.

#### Prerequisites
- AWS CLI installed and configured
- Docker installed
- AWS account with appropriate permissions

#### Deployment Steps

1. **Prepare your environment:**
   ```bash
   # Install AWS CLI if not already installed
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   
   # Configure AWS credentials
   aws configure
   ```

2. **Deploy to AWS:**
   ```bash
   # Make deployment script executable
   chmod +x deploy/aws/deploy.sh
   
   # Deploy to production
   ./deploy/aws/deploy.sh production us-east-1
   
   # Or deploy to development
   ./deploy/aws/deploy.sh development us-west-2
   ```

3. **Configure Exchange API Keys:**
   ```bash
   # Update ECS task definition with your API keys
   aws ecs update-service \
     --cluster sor-production-cluster \
     --service sor-production-service \
     --task-definition sor-production-task \
     --region us-east-1
   ```

#### AWS Architecture
- **ECS Fargate**: Serverless container hosting
- **RDS PostgreSQL**: Managed database
- **ElastiCache Redis**: Managed caching
- **Application Load Balancer**: Traffic distribution
- **CloudWatch**: Monitoring and logging
- **ECR**: Container registry

### Option 2: Heroku (Easiest for Quick Deploy)

Heroku is perfect for rapid prototyping and small-scale deployments.

#### Prerequisites
- Heroku CLI installed
- Git repository

#### Deployment Steps

1. **Install Heroku CLI:**
   ```bash
   # macOS
   brew install heroku/brew/heroku
   
   # Ubuntu/Debian
   curl https://cli-assets.heroku.com/install.sh | sh
   
   # Windows
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Deploy to Heroku:**
   ```bash
   # Make deployment script executable
   chmod +x deploy/heroku/deploy.sh
   
   # Deploy
   ./deploy/heroku/deploy.sh my-sor-app
   ```

3. **Configure Exchange API Keys:**
   ```bash
   # Set your exchange API keys
   heroku config:set GATE_API_KEY=your_gateio_key -a my-sor-app
   heroku config:set GATE_API_SECRET=your_gateio_secret -a my-sor-app
   heroku config:set MEXC_API_KEY=your_mexc_key -a my-sor-app
   heroku config:set MEXC_API_SECRET=your_mexc_secret -a my-sor-app
   ```

#### Heroku Features
- **PostgreSQL**: Managed database addon
- **Redis**: Managed caching addon
- **Papertrail**: Log management
- **Automatic scaling**: Based on traffic
- **SSL**: Automatic HTTPS

### Option 3: Google Cloud Platform

GCP offers excellent performance and integration with Google services.

#### Prerequisites
- Google Cloud SDK installed
- Docker installed
- GCP project with billing enabled

#### Deployment Steps

1. **Install Google Cloud SDK:**
   ```bash
   # Download and install
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   
   # Initialize
   gcloud init
   ```

2. **Deploy to GCP:**
   ```bash
   # Build and push to Google Container Registry
   gcloud builds submit --tag gcr.io/PROJECT_ID/sor-app
   
   # Deploy to Cloud Run
   gcloud run deploy sor-app \
     --image gcr.io/PROJECT_ID/sor-app \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

### Option 4: Azure Container Instances

Azure provides a simple way to run containers without managing infrastructure.

#### Prerequisites
- Azure CLI installed
- Docker installed
- Azure subscription

#### Deployment Steps

1. **Install Azure CLI:**
   ```bash
   # macOS
   brew install azure-cli
   
   # Ubuntu/Debian
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   
   # Windows
   # Download from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
   ```

2. **Deploy to Azure:**
   ```bash
   # Login to Azure
   az login
   
   # Create resource group
   az group create --name sor-rg --location eastus
   
   # Deploy container
   az container create \
     --resource-group sor-rg \
     --name sor-app \
     --image sor-app:latest \
     --ports 8000 \
     --environment-variables \
       DATABASE_URL=your_database_url \
       REDIS_URL=your_redis_url
   ```

## 🔧 Configuration

### Environment Variables

Set these environment variables for your deployment:

#### Required
```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Cache
REDIS_URL=redis://host:port/db

# Exchange API Keys
GATE_API_KEY=your_gateio_api_key
GATE_API_SECRET=your_gateio_secret
MEXC_API_KEY=your_mexc_api_key
MEXC_API_SECRET=your_mexc_secret
KUCOIN_API_KEY=your_kucoin_api_key
KUCOIN_SECRET=your_kucoin_secret
KUCOIN_PASSPHRASE=your_kucoin_passphrase
```

#### Optional
```bash
# Logging
LOG_LEVEL=INFO

# SOR Configuration
SOR_MAX_DAILY_VOLUME=100000
SOR_MAX_POSITION_SIZE=50000
SOR_MAX_SLIPPAGE=0.005

# Security
JWT_SECRET=your_jwt_secret
API_KEY=your_api_key
```

### Database Setup

The application will automatically create the required database schema on first run. The schema includes:

- **orders**: Main order records
- **order_executions**: Sub-order executions per venue
- **price_data**: Real-time price information
- **risk_metrics**: Risk management data
- **system_metrics**: Performance metrics
- **alerts**: System alerts and notifications

## 📊 Monitoring and Logging

### Health Checks

All deployments include health check endpoints:

- **Health Check**: `GET /health`
- **System Status**: `GET /system/health`
- **Detailed Stats**: `GET /system/stats`

### Logging

- **Application Logs**: Structured logging with configurable levels
- **Access Logs**: HTTP request/response logging
- **Error Tracking**: Comprehensive error logging and alerting

### Metrics

- **Order Execution**: Success rates, execution times, slippage
- **Venue Performance**: Per-exchange statistics
- **Risk Metrics**: Position tracking, exposure monitoring
- **System Health**: Resource usage, uptime, performance

## 🔒 Security Considerations

### Production Security Checklist

- [ ] Use HTTPS/TLS for all communications
- [ ] Implement proper authentication and authorization
- [ ] Store API keys securely (environment variables or secret management)
- [ ] Enable database encryption at rest
- [ ] Set up network security groups/firewalls
- [ ] Implement rate limiting
- [ ] Regular security updates and monitoring
- [ ] Backup and disaster recovery procedures

### API Security

The API includes several security features:

- **Rate Limiting**: Prevents abuse and ensures fair usage
- **Input Validation**: All inputs are validated using Pydantic
- **Error Handling**: Secure error responses without sensitive data
- **CORS Configuration**: Configurable cross-origin resource sharing

## 🚀 Scaling

### Horizontal Scaling

- **Load Balancers**: Distribute traffic across multiple instances
- **Auto Scaling**: Automatically adjust capacity based on demand
- **Database Read Replicas**: Distribute database read load

### Vertical Scaling

- **Resource Allocation**: Increase CPU/memory as needed
- **Database Optimization**: Tune database parameters for performance
- **Caching**: Implement Redis for frequently accessed data

## 🔄 CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Deploy to AWS
      run: |
        chmod +x deploy/aws/deploy.sh
        ./deploy/aws/deploy.sh production us-east-1
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## 📈 Performance Optimization

### Database Optimization

- **Indexing**: Proper indexes on frequently queried columns
- **Connection Pooling**: Efficient database connection management
- **Query Optimization**: Optimized SQL queries for better performance

### Caching Strategy

- **Redis Caching**: Cache frequently accessed data
- **API Response Caching**: Cache API responses where appropriate
- **Database Query Caching**: Cache expensive database queries

### Monitoring Performance

- **Application Performance Monitoring (APM)**: Track response times and bottlenecks
- **Database Performance**: Monitor query performance and slow queries
- **Resource Monitoring**: Track CPU, memory, and network usage

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Check database URL and credentials
   - Verify network connectivity
   - Check database server status

2. **Exchange API Issues**
   - Verify API keys and permissions
   - Check exchange API status
   - Review rate limiting settings

3. **Memory Issues**
   - Monitor memory usage
   - Adjust container memory limits
   - Optimize data structures

4. **Performance Issues**
   - Check database query performance
   - Monitor API response times
   - Review caching strategy

### Debug Commands

```bash
# View application logs
docker-compose logs -f sor-app

# Check database connectivity
docker-compose exec db psql -U sor_user -d sor_db -c "SELECT 1;"

# Test Redis connectivity
docker-compose exec redis redis-cli ping

# Check API health
curl http://localhost:8000/health
```

## 📞 Support

For deployment issues or questions:

1. Check the logs for error messages
2. Review the configuration settings
3. Test individual components
4. Consult the troubleshooting section
5. Open an issue on GitHub

## 🎯 Next Steps

After successful deployment:

1. **Configure Monitoring**: Set up comprehensive monitoring and alerting
2. **Security Hardening**: Implement additional security measures
3. **Performance Tuning**: Optimize based on usage patterns
4. **Backup Strategy**: Implement regular backups and disaster recovery
5. **Documentation**: Document your specific deployment configuration

---

**Happy Trading! 🚀**
