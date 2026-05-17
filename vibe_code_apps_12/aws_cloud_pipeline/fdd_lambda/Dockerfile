FROM public.ecr.aws/lambda/python:3.13

ARG DEPLOY_REVISION=1
RUN echo "deploy revision ${DEPLOY_REVISION}"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lambda_function.py .
COPY rules/ ${LAMBDA_TASK_ROOT}/rules/

CMD ["lambda_function.lambda_handler"]
