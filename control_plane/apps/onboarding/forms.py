from django import forms
from shared.crypto_utils import validate_and_fingerprint_ssh_key


class SSHPublicKeyForm(forms.Form):
    raw_key = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... user@host"}),
        label="OpenSSH Public Key",
        help_text="Provide a valid ssh-ed25519 or rsa-sha2-512 (>= 3072 bits) public key.",
    )

    def clean_raw_key(self) -> str:
        raw_key = self.cleaned_data.get("raw_key", "").strip()
        try:
            key_info = validate_and_fingerprint_ssh_key(raw_key)
            self.cleaned_key_info = key_info
        except ValueError as e:
            raise forms.ValidationError(str(e))
        return raw_key
