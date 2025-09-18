FROM opensearchproject/opensearch:latest

# Install the Skroutz Greek Stemmer plugin
# RUN bin/opensearch-plugin install --batch gr.skroutz:elasticsearch-skroutz-greekstemmer:7.7.0.1
RUN bin/opensearch-plugin install --batch analysis-icu

# Copy custom configuration if needed
COPY opensearch.yml /usr/share/opensearch/config/

# Install S3 plugin
RUN /usr/share/opensearch/bin/opensearch-plugin install --batch repository-s3

# Set env vars (these will be overridden by docker-compose at runtime)
ENV AWS_ACCESS_KEY_ID=changeme
ENV AWS_SECRET_ACCESS_KEY=changeme

# Add credentials to keystore at container start (not build time)
COPY --chmod=755 opensearch-entrypoint.sh /usr/share/opensearch/bin/opensearch-entrypoint.sh
ENTRYPOINT ["/usr/share/opensearch/bin/opensearch-entrypoint.sh"]