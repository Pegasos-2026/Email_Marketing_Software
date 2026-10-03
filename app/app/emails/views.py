from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from .services import send_email, create_sendgrid_domain_auth,check_domain_verification
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

        result = send_email(
            user=request.user,
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )

        if result.get("success"):
            return Response({"message": "Email sent successfully"})
        else:
            # Optional: include SendGrid status_code for debugging
            return Response(
                {
                    "error": "Email sending failed",
                    "status_code": result.get("status_code")
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class VerifyDomainView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            setting = request.user.emailsetting

            if not setting.sending_domain:
                return Response(
                    {"error": "Sending domain not configured"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            result = create_sendgrid_domain_auth(setting)
            setting.domain_id=result.get("domain_id")
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
    permission_classes=[IsAuthenticated]
    def get(self,request):
        try:
            setting=request.user.emailsetting
            if not setting.domain_id:
                return Response({"error":"Domain not created yet"},status=status.HTTP_400_BAD_REQUEST)
            is_verified=check_domain_verification(setting,setting.domain_id)
            if is_verified:
                setting.domain_verified=True
                setting.save()
            return Response({"domain_verified:",is_verified})
        except Exception as e:
            return Response({"error":str(e)},status=status.HTTP_400_BAD_REQUEST)
class EmailSettingView(generics.RetrieveUpdateAPIView):
    serializer_class=EmailSettingSerializer
    permission_classes=[IsAuthenticated]
    def get_object(self):
        obj, created=EmailSetting.objects.get_or_create(user=self.request.user)
        return obj