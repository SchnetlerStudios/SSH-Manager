from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from control_plane.apps.onboarding.forms import SSHPublicKeyForm
from control_plane.apps.onboarding.models import UserSSHPublicKey


@login_required
def register_ssh_key_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SSHPublicKeyForm(request.POST)
        if form.is_valid():
            key_info = form.cleaned_key_info
            UserSSHPublicKey.objects.filter(user=request.user, is_active=True).update(is_active=False)
            UserSSHPublicKey.objects.create(
                user=request.user,
                raw_key=key_info["raw_key"],
                algorithm=key_info["algorithm"],
                bits=key_info["bits"],
                fingerprint=key_info["fingerprint"],
                comment=key_info["comment"],
                is_active=True,
            )
            return redirect(request.GET.get("next") or "/access-requests/")
    else:
        form = SSHPublicKeyForm()

    return render(request, "onboarding/ssh_key_form.html", {"form": form})
