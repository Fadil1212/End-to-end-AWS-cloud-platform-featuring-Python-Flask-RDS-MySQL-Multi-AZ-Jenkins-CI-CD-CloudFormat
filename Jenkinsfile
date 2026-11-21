pipeline {
  agent any
  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 90, unit: 'MINUTES')
    skipDefaultCheckout(true)
  }
  parameters {
    string(name: 'DB_NAME', defaultValue: 'jj_nsrl', description: 'MySQL database name (e.g., your initials_nsrl).')
    string(name: 'STORAGE_GB', defaultValue: '20', description: 'RDS allocated storage in GiB (20 to 100).')
    choice(name: 'DB_INSTANCE_CLASS', choices: ['db.t3.micro', 'db.t3.small', 'db.t3.medium'], description: 'RDS compute class.')
    booleanParam(name: 'MULTI_AZ', defaultValue: true, description: 'Enable RDS MySQL Multi-AZ synchronous Standby DB for automatic failover.')
    string(name: 'VPC_ID', defaultValue: '', description: 'VPC containing the Jenkins host, Web App EC2, and RDS subnet group.')
    string(name: 'WEBAPP_SUBNET_ID', defaultValue: '', description: 'Public subnet ID (for outbound package access) hosting the private-access EC2 Python Web App Server.')
    string(name: 'DB_SUBNET_GROUP', defaultValue: '', description: 'Existing RDS DB subnet group NAME (not a subnet-... ID).')
    string(name: 'JENKINS_SECURITY_GROUP_ID', defaultValue: '', description: 'Security group ID attached to this Jenkins host.')
    string(name: 'STACK_NAME', defaultValue: 'nsrl-mysql-cloud', description: 'Unique CloudFormation stack name for RDS MySQL + EC2 Python Web App.')
    choice(name: 'AWS_REGION', choices: ['us-east-1', 'us-west-2'], description: 'AWS Academy Learner Lab region.')
    booleanParam(name: 'RUN_DEPLOYMENT', defaultValue: false, description: 'Check to deploy RDS MySQL + EC2 Web App Server, load NSRL from S3, and deploy the Python Web App.')
    booleanParam(name: 'RUN_FAILOVER_DR_TEST', defaultValue: false, description: 'Check to run live Multi-AZ failover, EC2 Web App reconnect check, and Snapshot DR restore.')
  }
  triggers { pollSCM('H/2 * * * *') }
  stages {
    stage('Checkout GitHub') {
      steps {
        script {
          def revision = checkout scm
          env.GIT_COMMIT = revision.GIT_COMMIT
        }
        sh 'mkdir -p artifacts'
      }
    }
    stage('CI checks') {
      steps {
        sh '''
          python3 -m unittest discover -s tests -v
          python3 -m compileall -q scripts app
          aws cloudformation validate-template --template-body file://infra/cloud-webapp.yaml >/dev/null
        '''
      }
    }
    stage('Validate parameters and network') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py preflight' }
    }
    stage('Deploy CloudFormation RDS + EC2 Web App') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py deploy' }
    }
    stage('Publish NSRL & Web App Bundle to S3') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py publish' }
    }
    stage('Extract and verify S3 release') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py download' }
    }
    stage('Load MySQL NSRL over TLS') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py load' }
    }
    stage('Verify MySQL NSRL & SSL') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py verify' }
    }
    stage('Deploy Python Web App Server on EC2') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py deploy_webapp' }
    }
    stage('Verify EC2 Python Web App & APIs') {
      when { expression { params.RUN_DEPLOYMENT } }
      steps { sh 'python3 scripts/workshop.py verify_webapp' }
    }
    stage('Standby Failover, Web App Reconnect & Snapshot DR') {
      when { expression { params.RUN_DEPLOYMENT && params.RUN_FAILOVER_DR_TEST } }
      steps { sh 'python3 scripts/workshop.py failover_dr' }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'artifacts/*.json', allowEmptyArchive: true
      deleteDir()
    }
  }
}
