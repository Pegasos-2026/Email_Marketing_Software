"""Server-Sent Events streams for live analytics updates."""
import json
import hashlib
import time

from django.http import StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from campaigns.analytics_service import AnalyticsService
from campaigns.models import Campaign


def _sse_message(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _stream_analytics(generator_fn, request):
    """Poll analytics every second; emit only when payload hash changes."""

    def event_stream():
        service = AnalyticsService()
        last_hash = None
        tick = 0
        try:
            while True:
                data = generator_fn(service, request)
                payload = json.dumps(data, default=str, sort_keys=True)
                digest = hashlib.md5(payload.encode()).hexdigest()
                tick += 1

                if digest != last_hash or tick == 1:
                    yield _sse_message('analytics', data)
                    last_hash = digest
                elif tick % 15 == 0:
                    yield _sse_message('ping', {'ts': time.time()})

                time.sleep(0.75)
        except GeneratorExit:
            return

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response


class DashboardAnalyticsStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        def load(service, req):
            return service.get_dashboard_overview(req.user)

        return _stream_analytics(load, request)


class CampaignAnalyticsStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        if not Campaign.objects.filter(id=campaign_id, user=request.user).exists():
            from rest_framework.response import Response
            return Response({'error': 'Not found'}, status=404)

        def load(service, req):
            return service.get_campaign_stats(campaign_id)

        return _stream_analytics(load, request)
