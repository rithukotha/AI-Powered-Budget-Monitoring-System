# app.py - Complete working version with all routes
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
from ocr_processor import OCRProcessor
import base64
from PIL import Image
import io
from flask_mail import Mail, Message
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import csv
from io import StringIO
from dateutil.relativedelta import relativedelta
from ai_recommendations import AIRecommendationEngine
# Add this new import
from collections import defaultdict
import numpy as np
import math
# Initialize OCR processor
ocr_processor = OCRProcessor()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
# Email configuration (add after other configs)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # For Gmail
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'kotharithika07@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'hrlj wnbw qwrd ctce'     # Replace with app password
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'

mail = Mail(app)

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    monthly_income = db.Column(db.Float, default=0)
    monthly_budget = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime)  # Remove default here
    receipt_image = db.Column(db.String(200))

class CategoryBudget(db.Model):
    __tablename__ = 'category_budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)

# Create database tables
with app.app_context():
    # Delete old database for fresh start (comment out after first run)
    # if os.path.exists('budget.db'):
    #     os.remove('budget.db')
    #     print("Old database removed")
    
    db.create_all()
    print("Database created with all tables")
    
    # Create a test user
    try:
        if not User.query.filter_by(email='test@example.com').first():
            test_user = User(
                name='Test User',
                email='test@example.com',
                password=generate_password_hash('test123', method='pbkdf2:sha256'),
                monthly_income=50000,
                monthly_budget=40000
            )
            db.session.add(test_user)
            db.session.commit()
            print("Test user created: test@example.com / test123")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating test user: {e}")

# Helper functions
def format_rupees(amount):
    return f"₹{amount:,.2f}"

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def calculate_financial_health(user, total_expenses, expenses, category_budgets):
    """Calculate financial health score based on multiple factors"""
    score = 0
    max_score = 100
    factors = {}
    
    if not user.monthly_income or user.monthly_income == 0:
        return {
            'score': 0,
            'factors': {'income': 'No income data available'},
            'status': 'poor',
            'savings_rate': 0
        }
    
    # Factor 1: Savings Rate (30 points)
    savings_rate = (user.monthly_income - total_expenses) / user.monthly_income * 100 if user.monthly_income > 0 else 0
    if savings_rate >= 30:
        score += 30
        factors['savings'] = f'Excellent savings rate: {savings_rate:.1f}%'
    elif savings_rate >= 20:
        score += 25
        factors['savings'] = f'Good savings rate: {savings_rate:.1f}%'
    elif savings_rate >= 10:
        score += 20
        factors['savings'] = f'Fair savings rate: {savings_rate:.1f}%'
    elif savings_rate >= 0:
        score += 10
        factors['savings'] = f'Low savings rate: {savings_rate:.1f}%'
    else:
        score += 0
        factors['savings'] = f'Overspending: {abs(savings_rate):.1f}% over income'
    
    # Factor: Budget Adherence (add this to your existing function)
    if user.monthly_budget and user.monthly_budget > 0:
        if total_expenses <= user.monthly_budget:
            score += 15
            factors['budget'] = 'Within monthly budget'
        elif total_expenses <= user.monthly_budget * 1.1:
            score += 10
            factors['budget'] = 'Slightly over budget'
        else:
            score += 5
            factors['budget'] = 'Over budget'

    # Factor 2: Budget Adherence (25 points)
    if category_budgets:
        budgets_ok = 0
        category_totals = {}
        for exp in expenses:
            if exp.category in category_totals:
                category_totals[exp.category] += exp.amount
            else:
                category_totals[exp.category] = exp.amount
                
        for budget in category_budgets:
            category_total = category_totals.get(budget.category, 0)
            if category_total <= budget.amount * 1.1:  # Within 10% of budget
                budgets_ok += 1
        
        if len(category_budgets) > 0:
            budget_score = (budgets_ok / len(category_budgets)) * 25
            score += budget_score
            factors['budgets'] = f'{budgets_ok}/{len(category_budgets)} categories within budget'
    else:
        score += 10  # Partial credit for having no budgets (but should set some)
        factors['budgets'] = 'Set category budgets to improve score'
    
    # Factor 3: Expense Consistency (20 points)
    if len(expenses) >= 10:
        # Calculate variance in expenses (more consistent = better)
        amounts = [exp.amount for exp in expenses[-20:]]  # Last 20 expenses
        if amounts:
            avg = sum(amounts) / len(amounts)
            variance = sum((a - avg) ** 2 for a in amounts) / len(amounts)
            if variance < avg * 0.3:  # Low variance
                score += 20
                factors['consistency'] = 'Very consistent spending pattern'
            elif variance < avg * 0.6:  # Medium variance
                score += 15
                factors['consistency'] = 'Moderately consistent spending'
            else:  # High variance
                score += 5
                factors['consistency'] = 'Irregular spending pattern detected'
    else:
        score += 5
        factors['consistency'] = 'Need more data for consistency analysis'
    
    # Factor 4: Tracking Consistency (15 points)
    if expenses:
        # Check if expenses are regularly logged (at least weekly)
        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)
        recent_expenses = [e for e in expenses if e.date >= thirty_days_ago]
        
        # Count unique weeks with expenses
        weeks_with_expenses = set()
        for exp in recent_expenses:
            week_num = exp.date.isocalendar()[1]
            weeks_with_expenses.add(week_num)
        
        weeks_covered = len(weeks_with_expenses)
        if weeks_covered >= 4:
            score += 15
            factors['tracking'] = 'Excellent tracking (weekly expenses)'
        elif weeks_covered >= 3:
            score += 10
            factors['tracking'] = 'Good tracking (3-4 weeks/month)'
        elif weeks_covered >= 2:
            score += 5
            factors['tracking'] = 'Fair tracking (2 weeks/month)'
        else:
            factors['tracking'] = 'Irregular expense tracking'
    else:
        factors['tracking'] = 'Start tracking expenses'
    
    # Factor 5: Emergency Fund Potential (10 points)
    if user.monthly_income > 0:
        emergency_months = (user.monthly_income - total_expenses) / (user.monthly_income * 0.7) if total_expenses < user.monthly_income else 0
        if emergency_months >= 6:
            score += 10
            factors['emergency'] = 'Excellent emergency fund potential'
        elif emergency_months >= 3:
            score += 7
            factors['emergency'] = 'Good emergency fund progress'
        elif emergency_months >= 1:
            score += 3
            factors['emergency'] = 'Building emergency fund'
        else:
            factors['emergency'] = 'Focus on building emergency fund'
    
    # Determine status based on score
    if score >= 80:
        status = 'excellent'
    elif score >= 60:
        status = 'good'
    elif score >= 40:
        status = 'fair'
    else:
        status = 'poor'
    
    return {
        'score': round(score),
        'factors': factors,
        'status': status,
        'savings_rate': round(savings_rate, 1)
    }


# Replace the generate_insights function with this enhanced version
def generate_enhanced_insights(user, total_expenses, expenses, category_dict, category_budgets):
    """Generate enhanced AI insights using the recommendation engine"""
    
    # Use the AIRecommendationEngine for personalized recommendations
    engine = AIRecommendationEngine(user, expenses, category_budgets)
    ai_recommendations = engine.generate_recommendations()
    
    # If we have AI recommendations, use them
    if ai_recommendations:
        # Convert to the format expected by the template
        insights = []
        for rec in ai_recommendations:
            insight = {
                'type': rec.get('type', 'info'),
                'icon': rec.get('icon', 'lightbulb'),
                'title': rec.get('title', 'AI Recommendation'),
                'message': rec.get('message', ''),
                'suggestion': rec.get('suggestion', ''),
                'priority': rec.get('priority', 3),
                'action': rec.get('action', ''),
                'category': rec.get('category', ''),  # ADD THIS
                'subscriptions': rec.get('subscriptions', [])  # ADD THIS
            }
            insights.append(insight)
        return insights
    
    # Fallback to basic insights if AI engine fails
    return generate_basic_insights(user, total_expenses, expenses, category_dict, category_budgets)

def generate_basic_insights(user, total_expenses, expenses, category_dict, category_budgets):
    """Basic insights as fallback"""
    insights = []
    
    if total_expenses > 0:
        if user.monthly_income and total_expenses > user.monthly_income:
            insights.append({
                'type': 'danger',
                'icon': 'exclamation-triangle',
                'title': '⚠️ Overspending Alert',
                'message': f'You exceeded your monthly income by {format_rupees(total_expenses - user.monthly_income)}',
                'suggestion': 'Review your expenses and identify areas to cut back.',
                'priority': 1
            })
        
        if category_dict:
            top_category = max(category_dict, key=category_dict.get)
            insights.append({
                'type': 'info',
                'icon': 'info-circle',
                'title': f'📊 Top Category: {top_category}',
                'message': f'Your highest spending category is {top_category}',
                'suggestion': f'Consider setting a budget for {top_category} to track better.',
                'priority': 2
            })
    else:
        insights.append({
            'type': 'info',
            'icon': 'lightbulb',
            'title': '✨ Get Started',
            'message': 'Add your first expense to receive personalized AI insights.',
            'suggestion': 'Start by adding today\'s expenses to see patterns.',
            'priority': 1
        })
    
    insights.sort(key=lambda x: x.get('priority', 3))
    return insights

# Update the dashboard route to use the enhanced insights
# Find this line in the dashboard function:
# insights = generate_insights(user, total_expenses, expenses, category_dict, category_budgets)

# Replace with:
#insights = generate_enhanced_insights(user, total_expenses, expenses, category_dict, category_budgets)

def predict_next_month_expenses(expenses, user):
    """Predict next month's expenses using multiple methods"""
    if len(expenses) < 3:
        return None, None, None
    
    # Get monthly totals for last 6 months
    monthly_totals = {}
    for exp in expenses:
        month_key = exp.date.strftime('%Y-%m')
        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + exp.amount
    
    # Sort months
    sorted_months = sorted(monthly_totals.keys())
    monthly_amounts = [monthly_totals[m] for m in sorted_months]
    
    if len(monthly_amounts) < 3:
        return None, None, None
    
    # Method 1: Simple moving average (last 3 months)
    avg_3_months = sum(monthly_amounts[-3:]) / 3
    
    # Method 2: Weighted average (more weight to recent months)
    weights = [0.5, 0.3, 0.2]  # Last 3 months weights
    weighted_avg = sum(a * w for a, w in zip(monthly_amounts[-3:], weights)) / sum(weights)
    
    # Method 3: Trend-based (linear growth)
    if len(monthly_amounts) >= 3:
        # Simple trend: average change
        changes = [monthly_amounts[i] - monthly_amounts[i-1] for i in range(1, len(monthly_amounts))]
        avg_change = sum(changes[-3:]) / 3 if len(changes) >= 3 else sum(changes) / len(changes)
        trend_based = monthly_amounts[-1] + avg_change
    else:
        trend_based = avg_3_months
    
    # Method 4: Seasonal (compare with same month last year)
    seasonal = None
    if len(sorted_months) >= 12:
        # This month last year
        last_year_month = (datetime.now().replace(year=datetime.now().year-1)).strftime('%Y-%m')
        if last_year_month in monthly_totals:
            seasonal = monthly_totals[last_year_month]
    
    # Combine predictions (weighted average)
    predictions = []
    weights_sum = 0
    
    if avg_3_months:
        predictions.append((avg_3_months, 0.3))
        weights_sum += 0.3
    
    if weighted_avg:
        predictions.append((weighted_avg, 0.4))
        weights_sum += 0.4
    
    if trend_based and trend_based > 0:
        predictions.append((trend_based, 0.2))
        weights_sum += 0.2
    
    if seasonal:
        predictions.append((seasonal, 0.1))
        weights_sum += 0.1
    
    if not predictions:
        return None, None, None
    
    # Final prediction
    final_prediction = sum(p * w for p, w in predictions) / weights_sum
    
    # Calculate confidence level
    if len(predictions) >= 3:
        # Check consistency between methods
        values = [p for p, _ in predictions]
        variance = sum((v - final_prediction) ** 2 for v in values) / len(values)
        if variance < final_prediction * 0.05:
            confidence = 'High'
        elif variance < final_prediction * 0.15:
            confidence = 'Medium'
        else:
            confidence = 'Low'
    else:
        confidence = 'Low'
    
    # Calculate min/max range
    min_pred = min(p for p, _ in predictions) * 0.9
    max_pred = max(p for p, _ in predictions) * 1.1
    
    # Category predictions
    category_predictions = {}
    category_totals = {}
    for exp in expenses:
        cat = exp.category or 'Other'
        if cat not in category_totals:
            category_totals[cat] = []
        category_totals[cat].append(exp.amount)
    
    for cat, amounts in category_totals.items():
        if len(amounts) >= 3:
            avg = sum(amounts[-3:]) / 3
            category_predictions[cat] = round(avg, 2)
    
    return {
        'prediction': round(final_prediction, 2),
        'range': (round(min_pred, 2), round(max_pred, 2)),
        'confidence': confidence,
        'methods_used': len(predictions),
        'category_predictions': category_predictions
    }, avg_3_months, weighted_avg

# AI Recommendation Engine Class
class AIRecommendationEngine:
    def __init__(self, user, expenses, category_budgets):
        self.user = user
        self.expenses = expenses
        self.category_budgets = {b.category: b.amount for b in category_budgets}
        self.category_totals = self._calculate_category_totals()
        self.total_expenses = sum(exp.amount for exp in expenses)
        self.avg_monthly_expense = self._calculate_avg_monthly()
        self.recommendations = []
        
    def _calculate_category_totals(self):
        totals = defaultdict(float)
        for exp in self.expenses:
            totals[exp.category or 'Other'] += exp.amount
        return dict(totals)
    
    def _calculate_avg_monthly(self):
        if not self.expenses:
            return 0
        
        # Group by month
        monthly_totals = defaultdict(float)
        for exp in self.expenses:
            month_key = exp.date.strftime('%Y-%m')
            monthly_totals[month_key] += exp.amount
        
        if monthly_totals:
            return sum(monthly_totals.values()) / len(monthly_totals)
        return 0
    
    def _get_spending_trends(self):
        """Analyze spending trends over time"""
        if len(self.expenses) < 5:
            return None
        
        # Sort expenses by date
        sorted_expenses = sorted(self.expenses, key=lambda x: x.date)
        
        # Calculate weekly averages
        weekly_totals = defaultdict(list)
        for exp in sorted_expenses[-30:]:  # Last 30 days
            week = exp.date.strftime('%Y-%W')
            weekly_totals[week].append(exp.amount)
        
        weekly_avgs = [sum(amounts)/len(amounts) for amounts in weekly_totals.values()]
        
        if len(weekly_avgs) >= 2:
            trend = (weekly_avgs[-1] - weekly_avgs[0]) / len(weekly_avgs)
            return {
                'direction': 'increasing' if trend > 0 else 'decreasing',
                'magnitude': abs(trend),
                'volatility': np.std(weekly_avgs) if len(weekly_avgs) > 1 else 0
            }
        return None
    
    def _get_category_trends(self):
        """Identify categories with unusual spending patterns"""
        if not self.expenses:
            return {}
        
        trends = {}
        categories = set(exp.category for exp in self.expenses)
        
        for category in categories:
            cat_expenses = [e for e in self.expenses if e.category == category]
            if len(cat_expenses) < 3:
                continue
            
            # Sort by date
            cat_expenses.sort(key=lambda x: x.date)
            
            # Get last 3 and previous 3
            recent = cat_expenses[-3:] if len(cat_expenses) >= 3 else cat_expenses
            older = cat_expenses[-6:-3] if len(cat_expenses) >= 6 else cat_expenses[:3]
            
            if recent and older:
                recent_avg = sum(e.amount for e in recent) / len(recent)
                older_avg = sum(e.amount for e in older) / len(older)
                
                change_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
                
                if abs(change_pct) > 20:  # Significant change
                    trends[category] = {
                        'change': change_pct,
                        'direction': 'up' if change_pct > 0 else 'down',
                        'recent_avg': recent_avg,
                        'older_avg': older_avg
                    }
        
        return trends
    
    def _calculate_savings_potential(self):
        """Calculate potential savings by category"""
        if not self.category_totals or not self.user.monthly_income:
            return []
        
        savings_opportunities = []
        
        # Define reasonable spending limits by category (as % of income)
        category_limits = {
            'Food & Dining': 0.15,      # 15% of income
            'Transportation': 0.10,      # 10% of income
            'Shopping': 0.08,             # 8% of income
            'Entertainment': 0.05,        # 5% of income
            'Bills & Utilities': 0.20,    # 20% of income
            'Healthcare': 0.05,            # 5% of income
            'Groceries': 0.12,             # 12% of income
            'Education': 0.05,              # 5% of income
            'Travel': 0.08,                 # 8% of income
            'Other': 0.07                   # 7% of income
        }
        
        for category, spent in self.category_totals.items():
            if category in category_limits:
                recommended = self.user.monthly_income * category_limits[category]
                if spent > recommended * 1.2:  # 20% over recommended
                    potential_savings = spent - recommended
                    savings_opportunities.append({
                        'category': category,
                        'spent': spent,
                        'recommended': recommended,
                        'potential_savings': potential_savings,
                        'percentage_over': ((spent - recommended) / recommended * 100)
                    })
        
        return sorted(savings_opportunities, key=lambda x: x['potential_savings'], reverse=True)
    
    def _detect_subscription_services(self):
        """Detect potential subscription services"""
        subscriptions = []
        
        # Common subscription keywords
        sub_keywords = ['netflix', 'spotify', 'amazon prime', 'youtube', 'disney+', 
                       'hotstar', 'sony liv', 'zee5', 'prime video', 'apple music',
                       'google one', 'icloud', 'dropbox', 'microsoft 365', 'canva',
                       'adobe', 'linkedin premium', 'medium', 'skillshare', 'udemy',
                       'gym', 'fitness', 'class', 'course', 'subscription']
        
        for exp in self.expenses:
            desc = (exp.description or '').lower()
            if any(keyword in desc for keyword in sub_keywords):
                subscriptions.append({
                    'name': exp.description or 'Unknown Subscription',
                    'amount': exp.amount,
                    'category': exp.category,
                    'date': exp.date
                })
        
        return subscriptions
    
    def generate_recommendations(self):
        """Generate personalized AI recommendations"""
        recommendations = []
        
        # 1. Savings opportunities based on overspending
        savings_ops = self._calculate_savings_potential()
        for op in savings_ops[:3]:  # Top 3 opportunities
            recommendations.append({
                'type': 'saving',
                'icon': 'piggy-bank',
                'title': f'💰 Save ₹{op["potential_savings"]:,.0f} on {op["category"]}',
                'message': f'You spent {op["percentage_over"]:.0f}% more than recommended ({op["category"]}: ₹{op["spent"]:,.0f} vs recommended ₹{op["recommended"]:,.0f}).',
                'suggestion': self._get_saving_suggestion(op['category']),
                'priority': 1 if op['potential_savings'] > 5000 else 2,
                'action': 'review_budget',
                'category': op['category']
            })
        
        # 2. Subscription analysis
        subscriptions = self._detect_subscription_services()
        if len(subscriptions) >= 3:
            total_sub_cost = sum(s['amount'] for s in subscriptions)
            yearly_cost = total_sub_cost * 12
            
            if yearly_cost > 5000:
                recommendations.append({
                    'type': 'subscription',
                    'icon': 'repeat',
                    'title': f'📱 You have {len(subscriptions)} active subscriptions',
                    'message': f'Total monthly subscription cost: ₹{total_sub_cost:,.0f} (₹{yearly_cost:,.0f}/year)',
                    'suggestion': 'Review unused subscriptions. Consider sharing family plans or switching to annual billing for discounts.',
                    'priority': 2,
                    'subscriptions': subscriptions[:5],
                    'action': 'review_subscriptions'
                })
        
        # 3. Category trends
        trends = self._get_category_trends()
        for category, trend in trends.items():
            if trend['direction'] == 'up' and trend['change'] > 30:
                recommendations.append({
                    'type': 'trend_warning',
                    'icon': 'chart-line',
                    'title': f'📈 {category} spending increasing rapidly',
                    'message': f'Your {category} expenses have increased by {trend["change"]:.0f}% recently (from ₹{trend["older_avg"]:,.0f} to ₹{trend["recent_avg"]:,.0f} per transaction).',
                    'suggestion': 'Track this category closely. Consider if this is a temporary increase or a new spending pattern.',
                    'priority': 2,
                    'action': 'monitor_spending',
                    'category': category
                })
        
        # 4. Emergency fund progress
        if self.user.monthly_income and self.user.monthly_income > 0:
            savings_rate = (self.user.monthly_income - self.total_expenses) / self.user.monthly_income * 100
            
            if savings_rate < 10:
                recommendations.append({
                    'type': 'emergency',
                    'icon': 'exclamation-triangle',
                    'title': '🚨 Emergency fund at risk',
                    'message': f'Your savings rate is only {savings_rate:.1f}%. Aim for at least 20% savings rate.',
                    'suggestion': 'Try the 50/30/20 rule: 50% needs, 30% wants, 20% savings. Track your "wants" category closely.',
                    'priority': 1,
                    'action': 'increase_savings'
                })
            elif savings_rate > 30:
                recommendations.append({
                    'type': 'investment',
                    'icon': 'chart-pie',
                    'title': '💹 Excellent savings rate!',
                    'message': f'You\'re saving {savings_rate:.1f}% of your income. Great job!',
                    'suggestion': 'Consider investing your surplus savings in mutual funds, PPF, or stocks for long-term wealth building.',
                    'priority': 3,
                    'action': 'explore_investments'
                })
        
        # 5. Category budget recommendations
        for category, spent in self.category_totals.items():
            if category in self.category_budgets:
                budget = self.category_budgets[category]
                if spent > budget:
                    overspend = spent - budget
                    days_left = (datetime.now().replace(day=28) - datetime.now()).days
                    daily_limit = (budget * 0.3) / max(days_left, 1) if days_left > 0 else 0
                    
                    recommendations.append({
                        'type': 'budget_alert',
                        'icon': 'exclamation-circle',
                        'title': f'⚠️ {category} budget exceeded by ₹{overspend:,.0f}',
                        'message': f'You\'ve spent ₹{spent:,.0f} of ₹{budget:,.0f} budget.',
                        'suggestion': f'To stay on track, limit daily {category} spending to ₹{daily_limit:,.0f} for the rest of the month.',
                        'priority': 1,
                        'action': 'adjust_spending',
                        'category': category
                    })
                elif spent > budget * 0.85:
                    remaining = budget - spent
                    recommendations.append({
                        'type': 'budget_warning',
                        'icon': 'hourglass-half',
                        'title': f'⏰ {category} budget running low',
                        'message': f'You\'ve used {(spent/budget*100):.1f}% of your {category} budget.',
                        'suggestion': f'Only ₹{remaining:,.0f} left for {category} this month. Plan your remaining expenses carefully.',
                        'priority': 2,
                        'action': 'monitor_spending',
                        'category': category
                    })
        
        # 6. Large expense detection
        if self.expenses:
            avg_expense = sum(e.amount for e in self.expenses) / len(self.expenses)
            large_expenses = [e for e in self.expenses if e.amount > avg_expense * 3]
            
            for exp in large_expenses[:2]:
                recommendations.append({
                    'type': 'large_expense',
                    'icon': 'bolt',
                    'title': f'💫 Large expense: ₹{exp.amount:,.0f} on {exp.category}',
                    'message': f'This is {exp.amount/avg_expense:.1f}x your average transaction.',
                    'suggestion': self._get_large_expense_suggestion(exp),
                    'priority': 2,
                    'action': 'review_expense'
                })
        
        # 7. Seasonal spending patterns
        current_month = datetime.now().month
        seasonal_suggestions = self._get_seasonal_suggestions(current_month)
        if seasonal_suggestions:
            recommendations.append(seasonal_suggestions)
        
        # Sort by priority (1 = highest)
        recommendations.sort(key=lambda x: x.get('priority', 3))
        
        return recommendations
    
    def _get_saving_suggestion(self, category):
        """Get specific saving suggestions per category"""
        suggestions = {
            'Food & Dining': 'Try meal prepping on weekends, use restaurant coupons, or limit dining out to weekends only. Consider using Swiggy One/Zomato Pro for discounts.',
            'Transportation': 'Consider carpooling, using public transport, or checking fuel prices across different stations. Apps like Park+ can help find cheaper parking.',
            'Shopping': 'Wait for sales (Amazon Great Indian, Flipkart Big Billion), use cashback apps like Cred or Paytm, and avoid impulse purchases with the 24-hour rule.',
            'Entertainment': 'Share OTT subscriptions with family/friends, look for student discounts, or explore free local events instead of paid ones.',
            'Bills & Utilities': 'Switch to energy-efficient appliances, unplug devices when not in use, and compare electricity plans. Consider solar for long-term savings.',
            'Healthcare': 'Opt for preventive care to avoid larger expenses, compare medicine prices on apps like 1mg or PharmEasy, and consider health insurance with higher coverage.',
            'Groceries': 'Shop at local markets for vegetables, buy in bulk for staples, use grocery apps for discounts, and plan meals to reduce food waste.',
            'Education': 'Look for free online resources (YouTube, Coursera audit), use library memberships, or share course subscriptions with friends.',
            'Travel': 'Book in advance, use incognito mode for flight searches, consider off-season travel, and use travel reward credit cards.',
            'Other': 'Track this category closely for a month and see if you can categorize expenses better to identify savings opportunities.'
        }
        return suggestions.get(category, 'Review your spending in this category and look for areas to cut back.')
    
    def _get_large_expense_suggestion(self, expense):
        """Get suggestion for a specific large expense"""
        if expense.category == 'Travel':
            return 'For future trips, consider booking during off-season, using travel reward cards, or splitting costs with friends.'
        elif expense.category == 'Shopping':
            return 'For expensive purchases, wait 24-48 hours before buying to avoid impulse decisions. Compare prices across platforms.'
        elif expense.category == 'Healthcare':
            return 'Check if this expense is covered by insurance. For future, consider preventive care and compare prices at different providers.'
        elif expense.category == 'Education':
            return 'Look for scholarships, payment plans, or employer reimbursement programs for educational expenses.'
        else:
            return 'Consider if this was a necessary expense or if there are more affordable alternatives for future purchases.'
    
    def _get_seasonal_suggestions(self, month):
        """Get seasonal spending suggestions"""
        seasonal_tips = {
            1: {  # January - New Year
                'title': '🎉 New Year Financial Reset',
                'message': 'Start the year strong with financial goals.',
                'suggestion': 'Review last year\'s spending, set new savings goals, and plan for upcoming tax-saving investments.',
                'icon': 'calendar-alt',
                'type': 'seasonal',
                'priority': 2,
                'action': 'plan_ahead'
            },
            3: {  # March - Financial year end
                'title': '📊 FY End Tax Planning',
                'message': 'Last chance for tax-saving investments.',
                'suggestion': 'Consider investing in ELSS, PPF, or tax-saving FDs before March 31st to maximize Section 80C benefits.',
                'icon': 'file-invoice',
                'type': 'seasonal',
                'priority': 2,
                'action': 'plan_ahead'
            },
            4: {  # April - New financial year
                'title': '📈 New Financial Year Planning',
                'message': 'Time to plan your investments for the year.',
                'suggestion': 'Set up SIPs, review insurance coverage, and plan your tax-saving investments early.',
                'icon': 'chart-line',
                'type': 'seasonal',
                'priority': 2,
                'action': 'plan_ahead'
            },
            10: {  # October - Festive season
                'title': '🎊 Festive Season Savings',
                'message': 'Smart shopping during festive sales.',
                'suggestion': 'Make a shopping list before sales, compare prices, and use festive discounts for planned purchases only.',
                'icon': 'gift',
                'type': 'seasonal',
                'priority': 2,
                'action': 'plan_ahead'
            },
            12: {  # December - Year end
                'title': '🎄 Year-End Financial Review',
                'message': 'Wrap up your finances for the year.',
                'suggestion': 'Review your spending patterns, maximize remaining tax-saving investments, and plan for the next year.',
                'icon': 'calendar-check',
                'type': 'seasonal',
                'priority': 2,
                'action': 'plan_ahead'
            }
        }
        
        if month in seasonal_tips:
            tip = seasonal_tips[month]
            return {
                'type': tip['type'],
                'icon': tip['icon'],
                'title': tip['title'],
                'message': tip['message'],
                'suggestion': tip['suggestion'],
                'priority': tip['priority'],
                'action': tip['action']
            }
        return None
    
# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email
            session.permanent = True
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not name or not email or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            monthly_income=0,
            monthly_budget=0
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one_or_none()
    
    # Get month from query parameter, default to current month
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    # Parse selected month
    try:
        year, month = map(int, selected_month.split('-'))
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    except:
        # Fallback to current month if parsing fails
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = datetime(start_date.year + 1, 1, 1)
        else:
            end_date = datetime(start_date.year, start_date.month + 1, 1)
        selected_month = start_date.strftime('%Y-%m')
    
    # Get expenses for selected month only
    expenses = db.session.execute(
        db.select(Expense)
        .filter_by(user_id=user_id)
        .filter(Expense.date >= start_date)
        .filter(Expense.date < end_date)
        .order_by(Expense.date.desc())
    ).scalars().all()
    
    # Get all expenses (for all-time calculations)
    all_expenses = db.session.execute(
        db.select(Expense).filter_by(user_id=user_id).order_by(Expense.date)
    ).scalars().all()
    
    # Create list of unique months with expenses
    available_months = []
    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    
    for exp in all_expenses:
        month_key = exp.date.strftime('%Y-%m')
        month_display = f"{month_names[exp.date.month]} {exp.date.year}"
        if month_key not in [m['value'] for m in available_months]:
            available_months.append({
                'value': month_key,
                'label': month_display
            })
    
    # Sort months in reverse chronological order (newest first)
    available_months.sort(key=lambda x: x['value'], reverse=True)
    
    # Calculate total expenses for the selected month
    total_expenses = sum(exp.amount for exp in expenses)
    
    # Calculate all-time total expenses
    total_expenses_all_time = sum(exp.amount for exp in all_expenses)
    
    # Calculate total savings from previous months
    months_since_created = 1
    if user and user.created_at:
        months_since_created = max(1, (datetime.now() - user.created_at).days // 30)
    
    total_income_estimate = (user.monthly_income or 0) * months_since_created
    total_savings = max(0, total_income_estimate - total_expenses_all_time)
    
    # Calculate category data for selected month
    category_dict = {}
    for exp in expenses:
        if exp.category:
            if exp.category in category_dict:
                category_dict[exp.category] += exp.amount
            else:
                category_dict[exp.category] = exp.amount
    
    category_data = {
        'labels': list(category_dict.keys()),
        'values': list(category_dict.values()),
        'colors': ['#FF6B6B', '#4ECDC4', '#FFD166', '#06D6A0', '#118AB2', '#EF476F', '#7209B7', '#3A86FF', '#FB5607']
    }
    
    # If no expenses for selected month, use dummy data
    if not expenses:
        category_data = {
            'labels': ['No expenses'],
            'values': [1],
            'colors': ['#e0e0e0']
        }
    
    # Monthly trends (for the line chart - show last 6 months)
    six_months_ago = start_date - timedelta(days=180)
    trend_expenses = db.session.execute(
        db.select(Expense)
        .filter_by(user_id=user_id)
        .filter(Expense.date >= six_months_ago)
        .order_by(Expense.date)
    ).scalars().all()
    
    monthly_totals = {}
    for exp in trend_expenses:
        month_key = exp.date.strftime('%Y-%m')
        if month_key in monthly_totals:
            monthly_totals[month_key] += exp.amount
        else:
            monthly_totals[month_key] = exp.amount
    
    # Sort months chronologically
    sorted_months = sorted(monthly_totals.keys())
    months_display = []
    for m in sorted_months:
        y, m_num = map(int, m.split('-'))
        months_display.append(f"{month_names[m_num][:3]} {y}")
    
    monthly_trends = {
        'months': months_display,
        'amounts': [monthly_totals[m] for m in sorted_months]
    }
    
    # Get category budgets
    category_budgets = db.session.execute(
        db.select(CategoryBudget).filter_by(user_id=user_id)
    ).scalars().all()
    
    # Calculate category totals for budget comparison
    category_totals = {}
    for exp in expenses:
        if exp.category:
            category_totals[exp.category] = category_totals.get(exp.category, 0) + exp.amount
    
    # Calculate budget progress for each category
    budget_progress = {}
    for budget in category_budgets:
        spent = category_totals.get(budget.category, 0)
        percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
        budget_progress[budget.category] = {
            'spent': spent,
            'percentage': round(percentage, 1),
            'remaining': max(0, budget.amount - spent),
            'status': 'danger' if percentage >= 100 else ('warning' if percentage >= 80 else 'success')
        }
    
    # Calculate financial health
    health_data = calculate_financial_health(user, total_expenses, all_expenses, category_budgets)
    health_score = health_data['score']
    health_factors = health_data['factors']
    health_status = health_data['status']
    
    # Generate enhanced insights
    insights = generate_enhanced_insights(user, total_expenses, expenses, category_dict, category_budgets)
    
    # Enhanced next month prediction
    prediction_data, avg_3_months, weighted_avg = predict_next_month_expenses(all_expenses, user)
    if prediction_data:
        next_month_prediction = prediction_data['prediction']
        prediction_range = prediction_data['range']
        prediction_confidence = prediction_data['confidence']
        category_predictions = prediction_data['category_predictions']
    else:
        next_month_prediction = None
        prediction_range = None
        prediction_confidence = None
        category_predictions = {}
    
    # Calculate previous and next months for navigation
    from dateutil.relativedelta import relativedelta
    current_date = datetime.strptime(selected_month + '-01', '%Y-%m-%d')
    prev_month_date = current_date - relativedelta(months=1)
    next_month_date = current_date + relativedelta(months=1)

    prev_month = prev_month_date.strftime('%Y-%m')
    next_month = next_month_date.strftime('%Y-%m')
    
    # Calculate savings for the stat cards
    if user and user.monthly_income:
        savings = user.monthly_income - total_expenses
    else:
        savings = 0

    total_category_budget = sum(b.amount for b in category_budgets) if category_budgets else 0
    total_category_spent = sum(category_totals.values())  
    
    return render_template(
        'dashboard.html',
        user=user,
        expenses=expenses,
        total_expenses=total_expenses,
        total_expenses_all_time=total_expenses_all_time,
        total_savings=total_savings,
        health_score=health_score,
        health_data=health_data,
        health_factors=health_factors,
        health_status=health_status,
        category_data=json.dumps(category_data),
        monthly_trends=json.dumps(monthly_trends),
        insights=insights,
        alerts=[],
        category_totals=category_totals,
        budget_progress=budget_progress,
        next_month_prediction=next_month_prediction,
        prediction_range=prediction_range,
        prediction_confidence=prediction_confidence,
        category_predictions=category_predictions,
        category_budgets=category_budgets,
        now=datetime.now(),
        format_rupees=format_rupees,
        available_months=available_months,
        selected_month=selected_month,
        month_display=start_date.strftime('%B %Y'),
        prev_month=prev_month,
        next_month=next_month,
        savings=savings,
        total_category_budget=total_category_budget,
        total_category_spent=total_category_spent
    )

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# API Endpoints
@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    try:
        user_id = session['user_id']
        amount = float(request.form.get('amount', 0))
        category = request.form.get('category', 'Other')
        description = request.form.get('description', '')
        date_str = request.form.get('date', '')
        
        # Get current month's expenses
        today = datetime.now()
        start_date = datetime(today.year, today.month, 1)
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1)
        else:
            end_date = datetime(today.year, today.month + 1, 1)
        
        current_month_expenses = db.session.execute(
            db.select(db.func.sum(Expense.amount))
            .filter_by(user_id=user_id)
            .filter(Expense.date >= start_date)
            .filter(Expense.date < end_date)
        ).scalar() or 0
        
        # Get all-time expenses (for savings calculation)
        all_time_expenses = db.session.execute(
            db.select(db.func.sum(Expense.amount))
            .filter_by(user_id=user_id)
        ).scalar() or 0
        
        # Get user
        user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one_or_none()
        
        if user and user.monthly_income > 0:
            # Calculate months since account creation
            months_since_created = 1
            if user.created_at:
                months_since_created = max(1, (datetime.now() - user.created_at).days // 30)
            
            # Calculate total income and available funds
            total_income = user.monthly_income * months_since_created
            total_savings = max(0, total_income - all_time_expenses)
            total_available = user.monthly_income + total_savings
            
            new_total_expenses = current_month_expenses + amount
            
            # STRICT CHECK: If expense exceeds total available funds, REJECT
            if new_total_expenses > total_available:
                excess = new_total_expenses - total_available
                return jsonify({
                    'success': False, 
                    'message': f'Cannot add expense! This would exceed your total available funds (income + savings) by ₹{excess:.2f}.'
                }), 400
        
        # Parse the date from the form
        if date_str:
            try:
                expense_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                expense_date = datetime.utcnow()
        else:
            expense_date = datetime.utcnow()
        
        expense = Expense(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            date=expense_date
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Expense added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_expense/<int:id>', methods=['DELETE'])
@login_required
def delete_expense(id):
    try:
        expense = db.session.execute(
            db.select(Expense).filter_by(id=id, user_id=session['user_id'])
        ).scalar_one_or_none()
        
        if expense:
            db.session.delete(expense)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Expense deleted successfully'})
        return jsonify({'success': False, 'message': 'Expense not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_income', methods=['POST'])
@login_required
def update_income():
    try:
        user_id = session['user_id']
        user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one_or_none()
        
        if user:
            user.monthly_income = float(request.form.get('monthly_income', 0))
            user.monthly_budget = float(request.form.get('monthly_budget', 0))
            db.session.commit()
            return jsonify({'success': True, 'message': 'Income updated successfully'})
        return jsonify({'success': False, 'message': 'User not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/predict_category', methods=['POST'])
@login_required
def predict_category():
    """Simple category prediction based on keywords"""
    try:
        data = request.get_json()
        text = data.get('text', '').lower()
        
        # Simple keyword-based categorization
        category_keywords = {
            'Food & Dining': ['food', 'restaurant', 'lunch', 'dinner', 'breakfast', 'cafe', 'pizza', 'burger', 'meal'],
            'Transportation': ['uber', 'ola', 'taxi', 'bus', 'train', 'metro', 'fuel', 'petrol', 'diesel', 'parking'],
            'Shopping': ['amazon', 'flipkart', 'shopping', 'clothes', 'electronics', 'mobile', 'laptop', 'store'],
            'Entertainment': ['movie', 'netflix', 'concert', 'game', 'theatre', 'music', 'sports'],
            'Bills & Utilities': ['electricity', 'water', 'bill', 'internet', 'wifi', 'broadband', 'recharge'],
            'Healthcare': ['doctor', 'hospital', 'medicine', 'pharmacy', 'medical', 'health', 'clinic'],
            'Groceries': ['grocery', 'vegetables', 'fruits', 'supermarket', 'store'],
            'Education': ['course', 'book', 'college', 'school', 'tuition', 'education'],
            'Travel': ['hotel', 'flight', 'trip', 'vacation', 'travel', 'booking']
        }
        
        predicted_category = 'Other'
        max_matches = 0
        
        for category, keywords in category_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text)
            if matches > max_matches:
                max_matches = matches
                predicted_category = category
        
        return jsonify({'success': True, 'category': predicted_category})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/ocr-test')
def ocr_test():
    """Test page for OCR functionality"""
    return render_template('ocr_test.html')

@app.route('/process_receipt', methods=['POST'])
@login_required
def process_receipt():
    """Process receipt using OCR"""
    try:
        # Add CSRF exemption if needed
        data = request.get_json()
        if not data or 'image_data' not in data:
            return jsonify({'success': False, 'message': 'No image data provided'}), 400
            
        image_data = data.get('image_data', '')
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            return jsonify({'success': False, 'message': 'Invalid image data format'}), 400
        
        # Create uploads directory if it doesn't exist with proper permissions
        os.makedirs('static/uploads', exist_ok=True)
        
        # Set proper permissions on uploads directory
        try:
            os.chmod('static/uploads', 0o755)  # rwxr-xr-x permissions
        except:
            pass
        
        # Create a unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"receipt_{timestamp}.jpg"
        filepath = os.path.join('static/uploads', filename)
        
        try:
            # Save image temporarily
            image = Image.open(io.BytesIO(image_bytes))
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            image.save(filepath, 'JPEG', quality=95)
            # Set file permissions
            os.chmod(filepath, 0o644)  # rw-r--r-- permissions
        except Exception as e:
            return jsonify({'success': False, 'message': f'Could not save image: {str(e)}'}), 500
        
        # Process receipt with OCR
        try:
            result = ocr_processor.process_receipt(filepath)
        except Exception as e:
            # Clean up file if OCR fails
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'success': False, 'message': f'OCR processing failed: {str(e)}'}), 500
        
        if result and result.get('success'):
            return jsonify({
                'success': True,
                'extracted_text': result.get('extracted_text', ''),
                'predicted_category': result.get('predicted_category', 'Other'),
                'extracted_amount': result.get('extracted_amount'),
                'extracted_date': result.get('extracted_date')
            })
        else:
            # Clean up file
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({
                'success': False,
                'message': result.get('message', 'Could not process receipt')
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/get_ai_recommendations', methods=['GET'])
@login_required
def get_ai_recommendations():
    """Generate AI recommendations based on spending patterns"""
    try:
        user_id = session['user_id']
        expenses = db.session.execute(
            db.select(Expense).filter_by(user_id=user_id)
        ).scalars().all()
        
        recommendations = []
        
        if expenses:
            # Calculate category totals
            category_totals = {}
            for exp in expenses:
                if exp.category in category_totals:
                    category_totals[exp.category] += exp.amount
                else:
                    category_totals[exp.category] = exp.amount
            
            # Find highest spending category
            if category_totals:
                max_category = max(category_totals, key=category_totals.get)
                max_amount = category_totals[max_category]
                
                recommendations.append({
                    'type': 'info',
                    'message': f'Your highest spending category is {max_category}',
                    'suggestion': f'Consider setting a budget for {max_category} to track your spending better.'
                })
            
            # Check for unusual spending
            avg_expense = sum(exp.amount for exp in expenses) / len(expenses)
            recent_expenses = expenses[:5]
            for exp in recent_expenses:
                if exp.amount > avg_expense * 2:
                    recommendations.append({
                        'type': 'warning',
                        'message': f'Large expense detected: {format_rupees(exp.amount)} on {exp.category}',
                        'suggestion': 'Review if this expense was necessary and plan accordingly.'
                    })
                    break
        
        if not recommendations:
            recommendations.append({
                'type': 'info',
                'message': 'Add more expenses to get personalized recommendations',
                'suggestion': 'Start by adding your daily expenses to get insights.'
            })
        
        return jsonify({'success': True, 'recommendations': recommendations})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/set_category_budget', methods=['POST'])
@login_required
def set_category_budget():
    try:
        user_id = session['user_id']
        category = request.form.get('category')
        amount = float(request.form.get('amount', 0))
        
        # Check if budget exists
        existing = db.session.execute(
            db.select(CategoryBudget).filter_by(user_id=user_id, category=category)
        ).scalar_one_or_none()
        
        if existing:
            if amount <= 0:  # Delete if amount is 0 or negative
                db.session.delete(existing)
                message = f'Budget for {category} deleted'
            else:
                existing.amount = amount
                message = f'Budget for {category} updated to {format_rupees(amount)}'
        else:
            if amount > 0:  # Only create if amount is positive
                budget = CategoryBudget(
                    user_id=user_id,
                    category=category,
                    amount=amount
                )
                db.session.add(budget)
                message = f'Budget set for {category}: {format_rupees(amount)}'
            else:
                return jsonify({'success': False, 'message': 'Amount must be greater than 0'})
        
        db.session.commit()
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/actionable_recommendations', methods=['GET'])
@login_required
def actionable_recommendations():
    """Get actionable recommendations with specific steps"""
    try:
        user_id = session['user_id']
        user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one_or_none()
        
        expenses = db.session.execute(
            db.select(Expense).filter_by(user_id=user_id)
        ).scalars().all()
        
        category_budgets = db.session.execute(
            db.select(CategoryBudget).filter_by(user_id=user_id)
        ).scalars().all()
        
        engine = AIRecommendationEngine(user, expenses, category_budgets)
        recommendations = engine.generate_recommendations()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/savings_tips/<category>', methods=['GET'])
@login_required
def get_savings_tips(category):
    """Get specific savings tips for a category"""
    
    tips = {
        'Food & Dining': [
            'Use apps like Swiggy One or Zomato Pro for discounts',
            'Try meal prepping on Sundays to avoid expensive takeaways',
            'Look for restaurant coupons on platforms like Nearbuy',
            'Limit dining out to weekends only',
            'Carry homemade lunch to work/school'
        ],
        'Transportation': [
            'Use public transport instead of cabs for daily commute',
            'Compare fuel prices across stations using apps like Park+',
            'Carpool with colleagues using apps like sRide or QuickRide',
            'Consider a monthly bus/train pass for discounts',
            'Maintain proper tire pressure to improve fuel efficiency'
        ],
        'Shopping': [
            'Wait for sales (Amazon Great Indian, Flipkart Big Billion)',
            'Use cashback apps like Cred or Paytm',
            'Apply the 24-hour rule before expensive purchases',
            'Unsubscribe from marketing emails to reduce temptation',
            'Compare prices across at least 3 platforms before buying'
        ],
        'Entertainment': [
            'Share OTT subscriptions with family/friends',
            'Look for student or annual discounts',
            'Explore free local events and community activities',
            'Use library memberships for books and movies',
            'Consider cheaper alternatives like YouTube for entertainment'
        ],
        'Bills & Utilities': [
            'Switch to LED bulbs to save electricity',
            'Unplug devices when not in use',
            'Compare electricity plans from different providers',
            'Install a smart power strip',
            'Use natural light during daytime'
        ],
        'Healthcare': [
            'Opt for preventive health checkups annually',
            'Compare medicine prices on apps like 1mg or PharmEasy',
            'Choose generic medicines when possible',
            'Maintain a separate emergency fund for health expenses',
            'Consider health insurance with higher coverage'
        ],
        'Groceries': [
            'Shop at local markets for fresh vegetables',
            'Buy staples in bulk during sales',
            'Use grocery apps for exclusive discounts',
            'Plan meals weekly to reduce food waste',
            'Avoid shopping when hungry'
        ],
        'Education': [
            'Look for free online courses on Coursera or edX',
            'Use library memberships for books',
            'Share course subscriptions with study partners',
            'Apply for scholarships and grants',
            'Consider buying used textbooks'
        ],
        'Travel': [
            'Book flights in incognito mode',
            'Travel during off-season for better rates',
            'Use travel reward credit cards',
            'Stay in hostels or homestays instead of hotels',
            'Book train tickets in advance for discounts'
        ]
    }
    
    category_tips = tips.get(category, [
        'Track this category for a month to identify patterns',
        'Set a realistic monthly budget',
        'Review if expenses in this category are necessary',
        'Look for alternative cheaper options',
        'Consider if this category aligns with your financial goals'
    ])
    
    return jsonify({
        'success': True,
        'category': category,
        'tips': category_tips
    })

@app.route('/export_expenses_email', methods=['POST'])
@login_required
def export_expenses_email():
    """Export current month expenses and send via email"""
    try:
        user_id = session['user_id']
        user = db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one_or_none()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Get email from request
        data = request.get_json()
        recipient_email = data.get('email', user.email)  # Default to user's email
        
        # Get current month expenses
        today = datetime.now()
        start_date = datetime(today.year, today.month, 1)
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1)
        else:
            end_date = datetime(today.year, today.month + 1, 1)
        
        expenses = db.session.execute(
            db.select(Expense)
            .filter_by(user_id=user_id)
            .filter(Expense.date >= start_date)
            .filter(Expense.date < end_date)
            .order_by(Expense.date)
        ).scalars().all()
        
        # Calculate totals
        total_expenses = sum(exp.amount for exp in expenses)
        
        # Create CSV in memory
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        
        # Write headers
        csv_writer.writerow(['Date', 'Category', 'Description', 'Amount (₹)', 'Receipt'])
        
        # Write expense data
        for exp in expenses:
            csv_writer.writerow([
                exp.date.strftime('%Y-%m-%d') if exp.date else '',
                exp.category or 'Other',
                exp.description or '',
                f"{exp.amount:.2f}",
                exp.receipt_image or ''
            ])
        
        # Write summary
        csv_writer.writerow([])
        csv_writer.writerow(['SUMMARY'])
        csv_writer.writerow(['Total Expenses', f"₹{total_expenses:.2f}"])
        csv_writer.writerow(['Number of Expenses', len(expenses)])
        csv_writer.writerow(['Month', today.strftime('%B %Y')])
        
        # Create email
        msg = Message(
            subject=f"Your Expense Report - {today.strftime('%B %Y')}",
            recipients=[recipient_email]
        )
        
        # Email body
        msg.body = f"""
Hello {user.name},

Here's your expense summary for {today.strftime('%B %Y')}:

📊 SUMMARY
═══════════════════════════════
Total Expenses: ₹{total_expenses:,.2f}
Number of Transactions: {len(expenses)}

📈 Category Breakdown:
"""
        
        # Add category breakdown
        categories = {}
        for exp in expenses:
            cat = exp.category or 'Other'
            categories[cat] = categories.get(cat, 0) + exp.amount
        
        for cat, amount in categories.items():
            percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
            msg.body += f"  • {cat}: ₹{amount:,.2f} ({percentage:.1f}%)\n"
        
        msg.body += f"""
═══════════════════════════════

The detailed CSV report is attached to this email.

Tips for next month:
• {get_spending_tip(categories, total_expenses)}
• Track your daily expenses to stay within budget
• Use the receipt scanner for automatic entry

Thank you for using AI Budget Monitor!

Best regards,
AI Budget Monitor Team
"""
        
        # Attach CSV
        csv_data = csv_buffer.getvalue()
        msg.attach(
            f"expenses_{today.strftime('%Y_%m')}.csv",
            'text/csv',
            csv_data
        )
        
        # Send email
        mail.send(msg)
        
        return jsonify({
            'success': True,
            'message': f'Expense report sent to {recipient_email}'
        })
        
    except Exception as e:
        print(f"Email error: {str(e)}")
        return jsonify({'success': False, 'message': f'Failed to send email: {str(e)}'})

def get_spending_tip(categories, total):
    """Generate a simple spending tip"""
    if not categories:
        return "Start tracking your expenses to get personalized tips"
    
    # Find highest category
    top_category = max(categories, key=categories.get)
    top_amount = categories[top_category]
    percentage = (top_amount / total * 100) if total > 0 else 0
    
    if percentage > 50:
        return f"Your {top_category} expenses are {percentage:.1f}% of total. Consider setting a budget for this category."
    elif total > 50000:  # Adjust threshold as needed
        return "Your total expenses are high. Try to identify areas where you can save."
    else:
        return f"You're doing great! Keep tracking your {top_category} expenses."
    
# Create necessary directories
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('static/uploads', exist_ok=True)




if __name__ == '__main__':
    app.run(debug=True, port=5001)