from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Wallet, WalletTransaction, WithdrawalRequest
from .services import WalletService

User = get_user_model()


class WalletModelTest(TestCase):
    """Test Wallet model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_wallet_creation(self):
        """Test wallet is created automatically"""
        self.assertTrue(hasattr(self.user, 'wallet'))
        self.assertEqual(self.user.wallet.available_balance, Decimal('0.00'))
    
    def test_total_balance(self):
        """Test total balance calculation"""
        wallet = self.user.wallet
        wallet.available_balance = Decimal('100.00')
        wallet.pending_balance = Decimal('50.00')
        wallet.held_balance = Decimal('25.00')
        wallet.save()
        
        self.assertEqual(wallet.total_balance, Decimal('175.00'))
    
    def test_can_withdraw(self):
        """Test withdrawal eligibility"""
        wallet = self.user.wallet
        wallet.available_balance = Decimal('100.00')
        wallet.save()
        
        self.assertTrue(wallet.can_withdraw(Decimal('50.00')))
        self.assertFalse(wallet.can_withdraw(Decimal('150.00')))


class WalletServiceTest(TestCase):
    """Test WalletService"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.wallet = self.user.wallet
    
    def test_credit_wallet(self):
        """Test crediting wallet"""
        initial_balance = self.wallet.available_balance
        
        WalletService.credit_wallet(
            self.wallet,
            Decimal('100.00'),
            'Test credit'
        )
        
        self.wallet.refresh_from_db()
        self.assertEqual(
            self.wallet.available_balance,
            initial_balance + Decimal('100.00')
        )
    
    def test_debit_wallet(self):
        """Test debiting wallet"""
        # Add funds first
        self.wallet.available_balance = Decimal('100.00')
        self.wallet.save()
        
        WalletService.debit_wallet(
            self.wallet,
            Decimal('50.00'),
            'Test debit'
        )
        
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('50.00'))
    
    def test_debit_insufficient_balance(self):
        """Test debiting with insufficient balance"""
        self.wallet.available_balance = Decimal('10.00')
        self.wallet.save()
        
        with self.assertRaises(ValueError):
            WalletService.debit_wallet(
                self.wallet,
                Decimal('50.00'),
                'Test debit'
            )
    
    def test_hold_funds(self):
        """Test holding funds"""
        self.wallet.available_balance = Decimal('100.00')
        self.wallet.save()
        
        WalletService.hold_funds(
            self.wallet,
            Decimal('50.00'),
            'Test hold'
        )
        
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('50.00'))
        self.assertEqual(self.wallet.held_balance, Decimal('50.00'))
    
    def test_release_funds(self):
        """Test releasing held funds"""
        self.wallet.available_balance = Decimal('50.00')
        self.wallet.held_balance = Decimal('50.00')
        self.wallet.save()
        
        WalletService.release_funds(
            self.wallet,
            Decimal('50.00'),
            'Test release'
        )
        
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('100.00'))
        self.assertEqual(self.wallet.held_balance, Decimal('0.00'))


class WithdrawalRequestTest(TestCase):
    """Test WithdrawalRequest model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.wallet = self.user.wallet
        self.wallet.available_balance = Decimal('1000.00')
        self.wallet.save()
    
    def test_withdrawal_creation(self):
        """Test creating withdrawal request"""
        withdrawal = WithdrawalRequest.objects.create(
            wallet=self.wallet,
            amount=Decimal('100.00'),
            withdrawal_method='bank_transfer',
            bank_account_name='Test Account',
            bank_account_number='1234567890',
            bank_name='Test Bank'
        )
        
        self.assertEqual(withdrawal.status, 'pending')
        self.assertGreater(withdrawal.processing_fee, Decimal('0.00'))
        self.assertLess(withdrawal.net_amount, withdrawal.amount)
    
    def test_withdrawal_fee_calculation(self):
        """Test withdrawal fee calculation"""
        withdrawal = WithdrawalRequest.objects.create(
            wallet=self.wallet,
            amount=Decimal('100.00'),
            withdrawal_method='esewa',
            bank_account_name='Test User',
            bank_account_number='9800000000',
            bank_name='eSewa',
        )
        
        # 1% fee
        expected_fee = Decimal('1.00')
        expected_net = Decimal('99.00')
        
        self.assertEqual(withdrawal.processing_fee, expected_fee)
        self.assertEqual(withdrawal.net_amount, expected_net)
