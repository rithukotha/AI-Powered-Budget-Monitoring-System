# ai_recommendations.py - Advanced AI Recommendation Engine
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import math

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
                'action': 'review_budget'
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
                    'action': 'monitor_category'
                })
        
        # 4. Emergency fund progress
        if self.user.monthly_income:
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
                        'action': 'adjust_spending'
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
                        'action': 'monitor_spending'
                    })
        
        # 6. Large expense detection with smart suggestions
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
        
        # 8. Peer comparison (simulated)
        if self.user.monthly_income and self.total_expenses > 0:
            peer_insight = self._get_peer_comparison()
            if peer_insight:
                recommendations.append(peer_insight)
        
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
                'suggestion': 'Review last year\'s spending, set new savings goals, and plan for upcoming tax-saving investments.'
            },
            3: {  # March - Financial year end
                'title': '📊 FY End Tax Planning',
                'message': 'Last chance for tax-saving investments.',
                'suggestion': 'Consider investing in ELSS, PPF, or tax-saving FDs before March 31st to maximize Section 80C benefits.'
            },
            4: {  # April - New financial year
                'title': '📈 New Financial Year Planning',
                'message': 'Time to plan your investments for the year.',
                'suggestion': 'Set up SIPs, review insurance coverage, and plan your tax-saving investments early.'
            },
            10: {  # October - Festive season
                'title': '🎊 Festive Season Savings',
                'message': 'Smart shopping during festive sales.',
                'suggestion': 'Make a shopping list before sales, compare prices, and use festive discounts for planned purchases only.'
            },
            12: {  # December - Year end
                'title': '🎄 Year-End Financial Review',
                'message': 'Wrap up your finances for the year.',
                'suggestion': 'Review your spending patterns, maximize remaining tax-saving investments, and plan for the next year.'
            }
        }
        
        if month in seasonal_tips:
            tip = seasonal_tips[month]
            return {
                'type': 'seasonal',
                'icon': 'calendar-alt',
                'title': tip['title'],
                'message': tip['message'],
                'suggestion': tip['suggestion'],
                'priority': 2,
                'action': 'plan_ahead'
            }
        return None
    
    def _get_peer_comparison(self):
        """Simulate peer comparison insights"""
        # This would ideally use anonymized data from other users
        # For now, we'll use rule-based comparisons
        
        # Define average spending percentages by category (as % of income)
        avg_percentages = {
            'Food & Dining': 12,
            'Transportation': 8,
            'Shopping': 7,
            'Entertainment': 5,
            'Bills & Utilities': 15,
            'Healthcare': 4,
            'Groceries': 10,
            'Education': 5,
            'Travel': 6
        }
        
        high_categories = []
        for category, spent in self.category_totals.items():
            if category in avg_percentages:
                percentage = (spent / self.user.monthly_income * 100) if self.user.monthly_income > 0 else 0
                avg_pct = avg_percentages[category]
                
                if percentage > avg_pct * 1.5:  # 50% higher than average
                    high_categories.append({
                        'category': category,
                        'your_pct': percentage,
                        'avg_pct': avg_pct,
                        'difference': percentage - avg_pct
                    })
        
        if high_categories:
            top = high_categories[0]
            return {
                'type': 'comparison',
                'icon': 'users',
                'title': f'👥 Compared to peers',
                'message': f'You spend {top["your_pct"]:.1f}% of income on {top["category"]} vs. average {top["avg_pct"]:.1f}%',
                'suggestion': f'Consider reducing {top["category"]} spending by about {top["difference"]:.1f}% of your income (₹{top["difference"]*self.user.monthly_income/100:,.0f}) to align with typical spending patterns.',
                'priority': 2,
                'action': 'review_category'
            }
        return None