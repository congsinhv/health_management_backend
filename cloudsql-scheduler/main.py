from googleapiclient import discovery
import functions_framework

PROJECT_ID = "vhealth-dev"


@functions_framework.http
def start_sql(request):
    """Start Cloud SQL instance"""
    request_json = request.get_json(silent=True)
    instance_name = request_json.get("instance") if request_json else None

    if not instance_name:
        return "Missing 'instance' in request body", 400

    service = discovery.build("sqladmin", "v1beta4")

    body = {"settings": {"activationPolicy": "ALWAYS"}}

    request = service.instances().patch(
        project=PROJECT_ID, instance=instance_name, body=body
    )
    response = request.execute()

    return f"Starting {instance_name}: {response.get('name', 'initiated')}"


@functions_framework.http
def stop_sql(request):
    """Stop Cloud SQL instance"""
    request_json = request.get_json(silent=True)
    instance_name = request_json.get("instance") if request_json else None

    if not instance_name:
        return "Missing 'instance' in request body", 400

    service = discovery.build("sqladmin", "v1beta4")

    body = {"settings": {"activationPolicy": "NEVER"}}

    request = service.instances().patch(
        project=PROJECT_ID, instance=instance_name, body=body
    )
    response = request.execute()

    return f"Stopping {instance_name}: {response.get('name', 'initiated')}"
