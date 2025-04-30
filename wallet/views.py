from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User

# Create your views here.

@login_required(login_url='login')
def home(request):
    return render(request, 'dashboard/home.html')


def register_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Basic validation
        if not (email and first_name and last_name and password1 and password2):
            messages.error(request, 'All fields are required.')
            return redirect('register')
            
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email is already taken.')
            return redirect('register')
            
        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password1
        )
        
        messages.success(request, 'Account created successfully. Please login.')
        return redirect('login')
        
    return render(request, 'authentication/register.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
            return redirect('login')
            
    return render(request, 'authentication/login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')



from decimal import Decimal
from django.db import transaction as db_transaction
from .models import Wallet, Transaction
from django.core.paginator import Paginator


@login_required
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    transactions = wallet.transactions.all().order_by('-timestamp')
    
    # Filtering
    transaction_type = request.GET.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    # Date filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        transactions = transactions.filter(timestamp__gte=start_date)
    if end_date:
        transactions = transactions.filter(timestamp__lte=end_date)
    
    # Pagination
    paginator = Paginator(transactions, 5)  # Show 5 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'wallet': wallet,
        'page_obj': page_obj,
        'transaction_types': dict(Transaction.TRANSACTION_TYPES),
    }
    return render(request, 'dashboard/wallet.html', context)

@login_required
def deposit_view(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be positive.')
                return redirect('deposit')
                
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            
            with db_transaction.atomic():
                wallet.balance += amount
                wallet.save()
                
                Transaction.objects.create(
                    wallet=wallet,
                    amount=amount,
                    transaction_type='deposit',
                    description=f"Deposit of ${amount}",
                    category_id=request.POST.get('category'),
                )
                
            messages.success(request, f'Successfully deposited ${amount}')
            return redirect('wallet')
            
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('deposit')
            
    return render(request, 'dashboard/deposite.html')

@login_required
def withdraw_view(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be positive.')
                return redirect('withdraw')
                
            wallet = Wallet.objects.get(user=request.user)
            
            if wallet.balance < amount:
                messages.error(request, 'Insufficient funds.')
                return redirect('withdraw')
                
            with db_transaction.atomic():
                wallet.balance -= amount
                wallet.save()
                
                Transaction.objects.create(
                    wallet=wallet,
                    amount=amount,
                    transaction_type='withdrawal',
                    description=f"Withdrawal of ${amount}",
                    category_id=request.POST.get('category'),
                )
                
            messages.success(request, f'Successfully withdrew ${amount}')
            return redirect('wallet')
            
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('withdraw')
            
    return render(request, 'dashboard/withdraw.html')

@login_required
def transfer_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        amount = request.POST.get('amount')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be positive.')
                return redirect('transfer')
                
            if email == request.user.email:
                messages.error(request, 'Cannot transfer to yourself.')
                return redirect('transfer')
                
            recipient = User.objects.get(email=email)
            sender_wallet = Wallet.objects.get(user=request.user)
            recipient_wallet, created = Wallet.objects.get_or_create(user=recipient)
            
            if sender_wallet.balance < amount:
                messages.error(request, 'Insufficient funds.')
                return redirect('transfer')
                
            with db_transaction.atomic():
                # Deduct from sender
                sender_wallet.balance -= amount
                sender_wallet.save()
                
                # Add to recipient
                recipient_wallet.balance += amount
                recipient_wallet.save()
                
                # Create transactions
                Transaction.objects.create(
                    wallet=sender_wallet,
                    amount=amount,
                    transaction_type='transfer',
                    description=f"Transfer to {recipient.email}",
                    recipient=recipient
                )
                
                Transaction.objects.create(
                    wallet=recipient_wallet,
                    amount=amount,
                    transaction_type='transfer',
                    description=f"Transfer from {request.user.email}",
                    recipient=request.user,
                    category_id=request.POST.get('category'),
                )
                
            messages.success(request, f'Successfully transferred ${amount} to {recipient.email}')
            return redirect('wallet')
            
        except User.DoesNotExist:
            messages.error(request, 'Recipient not found.')
            return redirect('transfer')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('transfer')
            
    return render(request, 'dashboard/transfer.html')


@login_required
def transaction_detail_view(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, wallet__user=request.user)
    return render(request, 'accounts/transaction_detail.html', {'transaction': transaction})





import csv
from django.http import HttpResponse
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

@login_required
def export_transactions_csv(request):
    wallet = Wallet.objects.get(user=request.user)
    transactions = wallet.transactions.all().order_by('-timestamp')
    
    # Apply filters if they exist
    transaction_type = request.GET.get('type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if start_date:
        transactions = transactions.filter(timestamp__gte=start_date)
    if end_date:
        transactions = transactions.filter(timestamp__lte=end_date)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Amount', 'Description', 'Recipient'])
    
    for t in transactions:
        writer.writerow([
            t.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            t.get_transaction_type_display(),
            f"${t.amount}",
            t.description,
            t.recipient.email if t.recipient else ''
        ])
    
    return response

@login_required
def export_transactions_pdf(request):
    wallet = Wallet.objects.get(user=request.user)
    transactions = wallet.transactions.all().order_by('-timestamp')
    
    # Apply filters if they exist
    transaction_type = request.GET.get('type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if start_date:
        transactions = transactions.filter(timestamp__gte=start_date)
    if end_date:
        transactions = transactions.filter(timestamp__lte=end_date)
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # PDF Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(1*inch, 10.5*inch, "Transaction History")
    p.setFont("Helvetica", 12)
    p.drawString(1*inch, 10*inch, f"Account: {request.user.email}")
    p.drawString(1*inch, 9.7*inch, f"Period: {start_date or 'Start'} to {end_date or 'End'}")
    p.drawString(1*inch, 9.4*inch, f"Current Balance: ${wallet.balance}")
    
    # Table Header
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1*inch, 9*inch, "Date")
    p.drawString(2.5*inch, 9*inch, "Type")
    p.drawString(4*inch, 9*inch, "Amount")
    p.drawString(5.5*inch, 9*inch, "Description")
    p.line(1*inch, 8.9*inch, 7.5*inch, 8.9*inch)
    
    # Table Content
    p.setFont("Helvetica", 10)
    y = 8.7*inch
    for t in transactions:
        if y < 1*inch:  # New page if we're at the bottom
            p.showPage()
            y = 9.5*inch
            # Repeat header on new page
            p.setFont("Helvetica-Bold", 10)
            p.drawString(1*inch, y, "Date")
            p.drawString(2.5*inch, y, "Type")
            p.drawString(4*inch, y, "Amount")
            p.drawString(5.5*inch, y, "Description")
            p.line(1*inch, y-0.1*inch, 7.5*inch, y-0.1*inch)
            y -= 0.3*inch
        
        p.drawString(1*inch, y, t.timestamp.strftime('%Y-%m-%d'))
        p.drawString(2.5*inch, y, t.get_transaction_type_display())
        p.drawString(4*inch, y, f"${t.amount}")
        p.drawString(5.5*inch, y, t.description[:30] + ('...' if len(t.description) > 30 else ''))
        y -= 0.25*inch
    
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="transactions.pdf"'
    return response


from .models import *

@login_required
def manage_categories(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            parent_id = request.POST.get('parent')
            
            if name:
                parent = Category.objects.get(id=parent_id) if parent_id else None
                Category.objects.create(
                    name=name,
                    user=request.user,
                    parent=parent
                )
                messages.success(request, 'Category added successfully.')
        
        elif action == 'delete':
            category_id = request.POST.get('category_id')
            Category.objects.filter(id=category_id, user=request.user).delete()
            messages.success(request, 'Category deleted successfully.')
            
        return redirect('manage_categories')
    
    categories = Category.objects.filter(user=request.user)
    return render(request, 'dashboard/manage_categories.html', {
        'categories': categories,
        'parent_categories': categories.filter(parent=None)
    })

@login_required
def manage_tags(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            if name:
                Tag.objects.create(name=name, user=request.user)
                messages.success(request, 'Tag added successfully.')
        
        elif action == 'delete':
            tag_id = request.POST.get('tag_id')
            Tag.objects.filter(id=tag_id, user=request.user).delete()
            messages.success(request, 'Tag deleted successfully.')
            
        return redirect('manage_tags')
    
    tags = Tag.objects.filter(user=request.user)
    return render(request, 'dashboard/manage_tags.html', {'tags': tags})





from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test


@login_required
def kyc_submission(request):
    try:
        kyc = request.user.kyc
    except KYCVerification.DoesNotExist:
        kyc = None

    if request.method == 'POST':
        # Basic validation
        document_type = request.POST.get('document_type')
        document_number = request.POST.get('document_number')
        document_front = request.FILES.get('document_front')
        document_back = request.FILES.get('document_back')
        selfie = request.FILES.get('selfie')

        if not all([document_type, document_number, document_front, selfie]):
            messages.error(request, 'Please fill all required fields')
            return redirect('kyc_submission')

        # Check file sizes
        for uploaded_file in [document_front, document_back, selfie]:
            if uploaded_file and uploaded_file.size > settings.MAX_UPLOAD_SIZE:
                messages.error(request, 'File size should not exceed 5MB')
                return redirect('kyc_submission')

        # Save or update KYC
        if kyc:
            kyc.document_type = document_type
            kyc.document_number = document_number
            kyc.status = 'pending'
            kyc.rejection_reason = ''
            if document_front:
                kyc.document_front = document_front
            if document_back:
                kyc.document_back = document_back
            if selfie:
                kyc.selfie = selfie
            kyc.save()
        else:
            kyc = KYCVerification.objects.create(
                user=request.user,
                document_type=document_type,
                document_number=document_number,
                document_front=document_front,
                document_back=document_back,
                selfie=selfie
            )

        messages.success(request, 'KYC documents submitted successfully!')
        return redirect('dashboard')

    context = {
        'kyc': kyc,
        'document_types': settings.ALLOWED_DOCUMENT_TYPES,
    }
    return render(request, 'verification/kyc_submission.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def kyc_review_list(request):
    pending_kycs = KYCVerification.objects.filter(status='pending')
    return render(request, 'verification/kyc_review_list.html', {'pending_kycs': pending_kycs})

@login_required
@user_passes_test(lambda u: u.is_staff)
def kyc_review_detail(request, kyc_id):
    kyc = get_object_or_404(KYCVerification, id=kyc_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            kyc.status = 'approved'
            kyc.reviewed_at = timezone.now()
            kyc.reviewer = request.user
            kyc.save()
            messages.success(request, 'KYC approved successfully')
            
        elif action == 'reject':
            reason = request.POST.get('rejection_reason')
            if not reason:
                messages.error(request, 'Please provide a rejection reason')
                return redirect('kyc_review_detail', kyc_id=kyc_id)
                
            kyc.status = 'rejected'
            kyc.reviewed_at = timezone.now()
            kyc.reviewer = request.user
            kyc.rejection_reason = reason
            kyc.save()
            messages.success(request, 'KYC rejected')
            
        return redirect('kyc_review_list')
    
    return render(request, 'verification/kyc_review_detail.html', {'kyc': kyc})