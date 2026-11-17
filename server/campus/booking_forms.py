from datetime import timedelta,datetime,time
from django import forms
from django.utils import timezone
from .models import Venue,TIME_SLOTS

def slot_start(day,slot):
    return timezone.make_aware(datetime.combine(day,time(int(slot),0)))

def can_book(day,slot):
    today=timezone.localdate()
    return today<=day<=today+timedelta(days=14) and slot_start(day,slot)>timezone.now()

class BookingForm(forms.Form):
    def __init__(self,*args,venue=None,**kwargs):
        self.venue=venue
        super().__init__(*args,**kwargs)

    day=forms.DateField(label='预约日期',widget=forms.HiddenInput)
    slot=forms.ChoiceField(label='预约时段',choices=TIME_SLOTS)
    request_key=forms.UUIDField(widget=forms.HiddenInput)

    def clean(self):
        data=super().clean()
        from .attendance import bookable
        allowed=bookable(self.venue,data['day'],data['slot']) if self.venue and 'day' in data and 'slot' in data else can_book(data['day'],data['slot']) if 'day' in data and 'slot' in data else True
        if not allowed:
            raise forms.ValidationError('请选择未来 14 天内尚未开始的时段。')
        return data

class VenueForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        # Older admin clients omit new layout fields; keep existing metadata on edit.
        data=args[0] if args else kwargs.get('data')
        if data is not None:
            data=data.copy();instance=kwargs.get('instance')
            for key,default in [('building','other'),('floor',1),('map_area','')]:
                if key not in data:data[key]=getattr(instance,key,default)
            if args:args=(data,*args[1:])
            else:kwargs['data']=data
        super().__init__(*args,**kwargs)
    class Meta:
        model=Venue
        fields=['name','kind','building','floor','map_area','location','description','active','is_demo']
        widgets={'description':forms.Textarea(attrs={'rows':3})}
