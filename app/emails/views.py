from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from .services import send_email, create_sendgrid_domain_auth, check_domain_verification, sync_sendgrid_domain_status
from .serializers import EmailSettingSerializer
from .models import EmailSetting

class SendEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subject = request.data.get("subject")
        html_content = request.data.get("html_content")
        to_email = request.data.get("to_email", request.user.email)

        if not subject or not html_content:
            return Response(
                {"error": "Subject and HTML content are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_email = None
        from_name = None
        reply_to = None
        try:
            setting = request.user.emailsetting
            from_email = setting.from_email
            from_name = setting.from_name
            reply_to = setting.from_email
        except EmailSetting.DoesNotExist:
            pass

        result = send_email(
            user=request.user,
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            is_test=True,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
        )

        if result.get("success"):
            return Response({"message": result.get("message", "Email sent successfully")})
        else:
            return Response(
                {
                    "error": result.get("error") or "Email sending failed",
                    "status_code": result.get("status_code"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class VerifyDomainView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            setting = request.user.emailsetting

            if setting.provider != "SendGrid":
                return Response(
                    {"error": "Domain verification is only available for SendGrid provider."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not setting.sending_domain:
                return Response(
                    {"error": "Sending domain not configured"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            result = create_sendgrid_domain_auth(setting)
            setting.domain_id = result.get("domain_id")
            setting.save()

            return Response(
                {
                    "message": "Add the following DNS records to your domain",
                    "domain": result.get("domain"),
                    "dns_records": result.get("dns_records")  # Ensure service.py returns this key
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            # Optional: log the exception for debugging
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class CheckDomainStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            setting = request.user.emailsetting
            verified, message = sync_sendgrid_domain_status(setting)
            return Response(
                {
                    "domain_verified": verified,
                    "domain": setting.sending_domain,
                    "message": message,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
class EmailSettingView(generics.RetrieveUpdateAPIView):
    serializer_class=EmailSettingSerializer
    permission_classes=[IsAuthenticated]
    def get_object(self):
        user = self.request.user
        obj, _created = EmailSetting.objects.get_or_create(
            user=user,
            defaults={
                'provider': 'SMTP',
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'smtp_user': user.email or '',
                'from_email': user.email or '',
                'from_name': user.get_full_name() or user.username or '',
            },
        )
        return obj