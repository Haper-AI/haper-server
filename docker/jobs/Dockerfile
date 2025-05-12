FROM public.ecr.aws/lambda/python:3.12

# Copy files
COPY . ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r requirements-jobs.txt

ENV PYTHONPATH=${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app/jobs/job_entry.handler" ]