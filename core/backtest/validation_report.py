"""
Backtest Validation Report
Validates backtest results for realism.
"""
import logging
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime

from .options_backtest import OptionsBacktestResult


@dataclass
class ValidationCheck:
    """Single validation check."""
    name: str
    passed: bool
    expected: str
    actual: str
    severity: str  # INFO, WARNING, ERROR


@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: datetime
    strategy_name: str
    total_checks: int
    passed: int
    failed: int
    is_valid: bool
    checks: List[ValidationCheck]
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "strategy_name": self.strategy_name,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "is_valid": self.is_valid,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "expected": c.expected,
                    "actual": c.actual,
                    "severity": c.severity
                }
                for c in self.checks
            ]
        }


class BacktestValidator:
    """
    Validates backtest results for realism.
    
    Flags suspicious results that may indicate:
    - Unrealistic fill assumptions
    - Missing theta decay
    - Missing IV modeling
    - Too-good-to-be-true performance
    """
    
    def __init__(self):
        self.logger = logging.getLogger("BacktestValidator")
    
    def validate(self, result: OptionsBacktestResult) -> ValidationReport:
        """
        Run all validation checks on backtest result.
        
        Args:
            result: Backtest result to validate
        
        Returns:
            ValidationReport with all checks
        """
        checks = []
        
        # Check 1: Spread realism
        checks.append(self._check_spread_realism(result))
        
        # Check 2: Theta realism (long options should pay theta)
        checks.append(self._check_theta_realism(result))
        
        # Check 3: IV variation
        checks.append(self._check_iv_variation(result))
        
        # Check 4: Fill realism
        checks.append(self._check_fill_realism(result))
        
        # Check 5: Win rate sanity
        checks.append(self._check_win_rate_sanity(result))
        
        # Check 6: P&L decomposition
        checks.append(self._check_pnl_decomposition(result))
        
        # Check 7: Trade frequency
        checks.append(self._check_trade_frequency(result))
        
        passed = sum(1 for c in checks if c.passed)
        failed = len(checks) - passed
        
        # Consider valid if no ERROR severity checks failed
        error_fails = sum(1 for c in checks if not c.passed and c.severity == "ERROR")
        is_valid = error_fails == 0
        
        report = ValidationReport(
            timestamp=datetime.now(),
            strategy_name=result.strategy_name,
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            is_valid=is_valid,
            checks=checks
        )
        
        self._log_report(report)
        
        return report
    
    def _check_spread_realism(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if spread costs are realistic."""
        avg_spread = result.avg_spread_cost
        
        # Options should have meaningful spread costs
        # Typical: ₹2-10 per lot for liquid options
        if avg_spread < 0.5:
            return ValidationCheck(
                name="Spread Realism",
                passed=False,
                expected="Avg spread > ₹0.50 per lot",
                actual=f"₹{avg_spread:.2f} (too low, likely unrealistic)",
                severity="ERROR"
            )
        elif avg_spread > 50:
            return ValidationCheck(
                name="Spread Realism",
                passed=False,
                expected="Avg spread < ₹50 per lot",
                actual=f"₹{avg_spread:.2f} (too high, check data)",
                severity="WARNING"
            )
        
        return ValidationCheck(
            name="Spread Realism",
            passed=True,
            expected="Avg spread ₹0.50-50 per lot",
            actual=f"₹{avg_spread:.2f}",
            severity="INFO"
        )
    
    def _check_theta_realism(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if theta decay is being tracked."""
        theta_cost = result.theta_decay_cost
        
        # Long options should pay theta
        # Check if any theta was recorded
        if theta_cost == 0 and result.total_trades > 0:
            return ValidationCheck(
                name="Theta Decay",
                passed=False,
                expected="Theta cost > 0 for long options",
                actual="₹0 (missing theta modeling)",
                severity="ERROR"
            )
        
        return ValidationCheck(
            name="Theta Decay",
            passed=True,
            expected="Positive theta cost for longs",
            actual=f"₹{theta_cost:.2f}",
            severity="INFO"
        )
    
    def _check_iv_variation(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if IV changes are being tracked."""
        iv_impact = result.iv_change_impact
        
        # IV impact should vary (not always zero)
        if iv_impact == 0 and result.total_trades > 5:
            return ValidationCheck(
                name="IV Modeling",
                passed=False,
                expected="Non-zero IV impact over 5+ trades",
                actual="₹0 (IV not being tracked)",
                severity="WARNING"
            )
        
        return ValidationCheck(
            name="IV Modeling",
            passed=True,
            expected="Variable IV impact",
            actual=f"₹{iv_impact:.2f}",
            severity="INFO"
        )
    
    def _check_fill_realism(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if fills are realistic (not 100%)."""
        fill_rate = result.fill_rate
        
        # 100% fill rate is suspicious
        if fill_rate >= 100:
            return ValidationCheck(
                name="Fill Realism",
                passed=False,
                expected="Fill rate < 100%",
                actual=f"{fill_rate:.1f}% (unrealistic, some orders should fail)",
                severity="WARNING"
            )
        elif fill_rate < 50:
            return ValidationCheck(
                name="Fill Realism",
                passed=False,
                expected="Fill rate > 50%",
                actual=f"{fill_rate:.1f}% (too low, check aggression)",
                severity="WARNING"
            )
        
        return ValidationCheck(
            name="Fill Realism",
            passed=True,
            expected="Fill rate 50-99%",
            actual=f"{fill_rate:.1f}%",
            severity="INFO"
        )
    
    def _check_win_rate_sanity(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if win rate is reasonable."""
        win_rate = result.win_rate
        
        # Win rate > 80% is suspicious for options
        if win_rate > 80:
            return ValidationCheck(
                name="Win Rate Sanity",
                passed=False,
                expected="Win rate < 80%",
                actual=f"{win_rate:.1f}% (suspiciously high)",
                severity="WARNING"
            )
        
        return ValidationCheck(
            name="Win Rate Sanity",
            passed=True,
            expected="Win rate < 80%",
            actual=f"{win_rate:.1f}%",
            severity="INFO"
        )
    
    def _check_pnl_decomposition(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if P&L components sum correctly."""
        delta = result.total_delta_pnl
        theta = result.theta_decay_cost
        iv = result.iv_change_impact
        spread = result.spread_slippage_cost
        net = result.total_pnl
        
        # Net should ≈ Delta - Theta + IV - Spread
        expected_net = delta - theta + iv - spread
        diff = abs(net - expected_net)
        
        # Allow 5% tolerance
        tolerance = abs(net) * 0.05 if net != 0 else 100
        
        if diff > tolerance:
            return ValidationCheck(
                name="P&L Decomposition",
                passed=False,
                expected=f"Net ≈ Delta - Theta + IV - Spread",
                actual=f"Diff=₹{diff:.0f} (components don't add up)",
                severity="WARNING"
            )
        
        return ValidationCheck(
            name="P&L Decomposition",
            passed=True,
            expected="Components sum to net P&L",
            actual=f"✓ Verified (diff=₹{diff:.0f})",
            severity="INFO"
        )
    
    def _check_trade_frequency(self, result: OptionsBacktestResult) -> ValidationCheck:
        """Check if trade frequency is reasonable."""
        trades = result.total_trades
        
        if trades == 0:
            return ValidationCheck(
                name="Trade Frequency",
                passed=False,
                expected="At least 1 trade",
                actual="0 trades (check strategy signals)",
                severity="ERROR"
            )
        
        # Calculate trades per day
        if result.start_date and result.end_date:
            days = (result.end_date - result.start_date).days or 1
            trades_per_day = trades / days
            
            if trades_per_day > 10:
                return ValidationCheck(
                    name="Trade Frequency",
                    passed=False,
                    expected="< 10 trades per day",
                    actual=f"{trades_per_day:.1f}/day (overtrading)",
                    severity="WARNING"
                )
        
        return ValidationCheck(
            name="Trade Frequency",
            passed=True,
            expected="Reasonable trading frequency",
            actual=f"{trades} trades",
            severity="INFO"
        )
    
    def _log_report(self, report: ValidationReport):
        """Log validation report."""
        if report.is_valid:
            self.logger.info(f"✅ Backtest VALID: {report.passed}/{report.total_checks} checks passed")
        else:
            self.logger.warning(f"❌ Backtest INVALID: {report.failed} checks failed")
            for check in report.checks:
                if not check.passed:
                    self.logger.warning(f"  [{check.severity}] {check.name}: {check.actual}")
    
    def print_report(self, report: ValidationReport):
        """Print formatted validation report."""
        print("\n" + "=" * 60)
        print("  BACKTEST VALIDATION REPORT")
        print("=" * 60)
        print(f"  Strategy: {report.strategy_name}")
        print(f"  Time: {report.timestamp}")
        print("-" * 60)
        
        status = "✅ VALID" if report.is_valid else "❌ INVALID"
        print(f"  Status: {status}")
        print(f"  Checks: {report.passed}/{report.total_checks} passed")
        print("-" * 60)
        
        for check in report.checks:
            icon = "✅" if check.passed else "❌"
            print(f"  {icon} {check.name}")
            print(f"     Expected: {check.expected}")
            print(f"     Actual: {check.actual}")
        
        print("=" * 60 + "\n")


# Singleton
backtest_validator = BacktestValidator()
