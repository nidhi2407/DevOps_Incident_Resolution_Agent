FROM jenkins/jenkins:lts

USER root
RUN apt-get update && apt-get install -y ca-certificates curl docker.io && \
    ln -s /usr/bin/docker /usr/local/bin/docker && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory '*'

USER jenkins
