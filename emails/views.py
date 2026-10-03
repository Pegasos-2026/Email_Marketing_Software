from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response

from rest_framework import status

from .services import send_email, create_sendgrid_domain_auth

from .services_local import send_email_local, create_sendgrid_domain_auth as create_domain_auth_local

from .services_real_gmail import send_email_real_gmail, create_sendgrid_domain_auth_gmail as create_domain_auth_gmail





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



        # Use real Gmail SMTP service for actual email delivery

        result = send_email_real_gmail(

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



            result = create_domain_auth_local(setting)



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

