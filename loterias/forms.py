from django import forms

from .services import InvalidPick, validate_pick


class TicketForm(forms.Form):
    """Volante da aposta mínima: números (ou colunas) e o extra, quando houver."""

    def __init__(self, lottery, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.lottery = lottery
        if lottery.kind == "colunas":
            digits = [(str(d), str(d)) for d in range(10)]
            for column in range(1, lottery.columns + 1):
                self.fields[f"c{column}"] = forms.TypedChoiceField(
                    label=f"Coluna {column}", choices=digits, coerce=int, required=False, widget=forms.RadioSelect
                )
        else:
            self.fields["n"] = forms.TypedMultipleChoiceField(
                label="Números",
                choices=[(str(i), f"{i:0{lottery.digits}d}") for i in lottery.numbers],
                coerce=int,
                required=False,
                widget=forms.CheckboxSelectMultiple,
            )
        extra = lottery.extra
        if extra is not None and extra.playable:
            if extra.options:
                self.fields["extra"] = forms.TypedChoiceField(
                    label=extra.label,
                    choices=[("", "Escolha")] + [(str(i + 1), name) for i, name in enumerate(extra.options)],
                    coerce=int,
                    required=False,
                )
            else:
                self.fields["extra"] = forms.TypedMultipleChoiceField(
                    label=extra.label,
                    choices=[(str(i), str(i)) for i in range(1, extra.pool + 1)],
                    coerce=int,
                    required=False,
                    widget=forms.CheckboxSelectMultiple,
                )

    @property
    def columns(self):
        return [self[f"c{column}"] for column in range(1, self.lottery.columns + 1)]

    def clean(self):
        data = super().clean()
        if self.lottery.kind == "colunas":
            numbers = [data.get(f"c{column}") for column in range(1, self.lottery.columns + 1)]
            if any(value in (None, "") for value in numbers):
                raise forms.ValidationError(f"Marque um dígito em cada uma das {self.lottery.columns} colunas.")
        else:
            numbers = data.get("n") or []
        extra = data.get("extra")
        if extra in (None, ""):
            extra = []
        elif not isinstance(extra, list):
            extra = [extra]
        try:
            data["numbers"], data["extra_list"] = validate_pick(self.lottery, numbers, extra)
        except InvalidPick as exc:
            raise forms.ValidationError(str(exc)) from exc
        return data
