#!/usr/bin/env bash
# Wait for Jenkins to be up
while ! curl -s http://localhost:8080/login > /dev/null; do
  echo "Waiting for Jenkins..."
  sleep 5
done
# Install required plugins using Jenkins CLI
JENKINS_CLI="java -jar /var/jenkins_home/jenkins-cli.jar -s http://localhost:8080"
$JENKINS_CLI install-plugin workflow-aggregator git docker-workflow credentials-binding -restart
# Restart Jenkins to apply plugins
$JENKINS_CLI safe-restart
