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
                    description=f"Deposit of ${amount}"
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
                    description=f"Withdrawal of ${amount}"
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
                    recipient=request.user
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