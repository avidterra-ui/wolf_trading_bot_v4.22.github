"""
Main entry point for Wolf Trading Bot.
Telegram → BingX Auto-Trading System v4.1

CRITICAL v4.1 Features:
- VIP signals: Direction from OCR, TP/SL always manual
- FREE signals: Direction from Regex, TP/SL from signal or manual
- Max trades per day limit
- STRICT Limit Orders only - NO MARKET ORDERS
"""

import asyncio
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .startup import interactive_startup, display_running_status
from .models import TelegramConfig, RuntimeConfig, TradeSignal
from .telegram_client import TelegramMonitor, create_telegram_session
from .bingx_client import SecureBingXClient
from .trade_executor import TradeExecutor, DryRunExecutor
from .utils.logging_setup import setup_logging, get_logger
from .utils.security import SecureConfigLoader

console = Console()
logger = get_logger(__name__)


class WolfTradingBot:
    """
    Main bot controller that orchestrates all components.
    """
    
    def __init__(self):
        self.config_loader = SecureConfigLoader()
        self.runtime_config: RuntimeConfig = None
        self.telegram_monitor: TelegramMonitor = None
        self.trade_executor: TradeExecutor = None
        self.bingx_client: SecureBingXClient = None
        self._running = False
    
    async def setup(self) -> bool:
        """
        Setup all components.
        
        Returns:
            True if setup successful
        """
        try:
            # Load configuration
            config = self.config_loader.load_config()
            
            # Create Telegram config
            telegram_config = TelegramConfig(
                api_id=int(config['telegram']['api_id']),
                api_hash=config['telegram']['api_hash'],
                session_name=config['telegram'].get('session_name', 'wolf_trading_bot'),
                public_channel_username=config['telegram']['public_channel'].get('username', 'thewolfofcrypto1'),
                public_channel_title=config['telegram']['public_channel'].get('title', 'THE WOLF (CRYPTO)'),
                vip_channel_title=config['telegram']['vip_channel'].get('title', 'WOLF OFFICIAL VIP'),
            )
            
            # Interactive startup configuration
            self.runtime_config = await interactive_startup()
            
            # Get tesseract path for Windows
            tesseract_cmd = config.get('ocr', {}).get('tesseract_cmd')
            
            # Create Telegram monitor
            self.telegram_monitor = TelegramMonitor(
                config=telegram_config,
                runtime_config=self.runtime_config,
                tesseract_cmd=tesseract_cmd,
            )
            
            # Create trade executor
            if self.runtime_config.dry_run:
                # Use dry run executor (no BingX client needed)
                self.trade_executor = DryRunExecutor(self.runtime_config)
            else:
                # Create BingX client for live trading
                bingx_api_key = SecureConfigLoader.require_env('BINGX_API_KEY')
                bingx_api_secret = SecureConfigLoader.require_env('BINGX_API_SECRET')
                
                self.bingx_client = SecureBingXClient(
                    api_key=bingx_api_key,
                    api_secret=bingx_api_secret,
                )
                
                # Test API connection first
                logger.info("Testing BingX API connection...")
                success, message = await self.bingx_client.test_connection()
                if success:
                    console.print("[green]✓[/green] BingX API connection successful")
                else:
                    console.print(f"[bold red]API connection failed: {message}[/bold red]")
                    console.print("[yellow]Please check your API key and secret[/yellow]")
                    return False
                
                # Initialize contracts cache for symbol validation
                logger.info("Initializing BingX contracts cache...")
                if not await self.bingx_client.initialize_contracts_cache():
                    console.print("[bold red]Failed to initialize BingX contracts cache[/bold red]")
                    console.print("[yellow]Symbol validation may not work properly[/yellow]")
                else:
                    console.print("[green]✓[/green] BingX contracts cache initialized")
                
                self.trade_executor = TradeExecutor(
                    bingx_client=self.bingx_client,
                    config=self.runtime_config,
                )
            
            # Register signal handler
            self.telegram_monitor.add_signal_handler(self._on_signal)
            
            return True
            
        except FileNotFoundError as e:
            console.print(f"[bold red]Configuration file not found: {e}[/bold red]")
            console.print("[yellow]Please create config/config.yaml from config.example.yaml[/yellow]")
            return False
            
        except ValueError as e:
            console.print(f"[bold red]Configuration error: {e}[/bold red]")
            return False
            
        except Exception as e:
            console.print(f"[bold red]Setup failed: {e}[/bold red]")
            logger.exception("Setup failed")
            return False
    
    async def _on_signal(self, signal: TradeSignal):
        """Handle incoming trading signal."""
        try:
            await self.trade_executor.execute_signal(signal)
        except Exception as e:
            logger.exception(f"Signal execution failed: {e}")
    
    async def run(self):
        """Run the bot."""
        self._running = True
        
        try:
            # Connect to Telegram
            if not await self.telegram_monitor.connect():
                console.print("[bold red]Failed to connect to Telegram[/bold red]")
                return
            
            # Display running status
            channel_title = getattr(
                self.telegram_monitor.channel_entity,
                'title',
                'THE WOLF (CRYPTO)'
            )
            display_running_status(self.runtime_config, channel_title)
            
            # Start monitoring
            await self.telegram_monitor.start_monitoring()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        except Exception as e:
            logger.exception(f"Bot error: {e}")
            console.print(f"[bold red]Bot error: {e}[/bold red]")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the bot."""
        self._running = False
        
        console.print("\n[cyan]Shutting down Wolf Trading Bot...[/cyan]")
        
        if self.telegram_monitor:
            await self.telegram_monitor.disconnect()
        
        if self.bingx_client:
            await self.bingx_client.close()
        
        # Print statistics
        if self.trade_executor:
            console.print(f"\n[dim]Statistics: {self.trade_executor.get_stats_summary()}[/dim]")
        
        console.print("[green]Goodbye! 🐺[/green]")


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging(log_dir="logs")
    
    # Check for auth command
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        # Run Telegram authentication
        config_loader = SecureConfigLoader()
        try:
            config = config_loader.load_config()
            await create_telegram_session(
                api_id=int(config['telegram']['api_id']),
                api_hash=config['telegram']['api_hash'],
            )
        except Exception as e:
            console.print(f"[bold red]Authentication failed: {e}[/bold red]")
        return
    
    # Create and run bot
    bot = WolfTradingBot()
    
    if await bot.setup():
        await bot.run()


def run():
    """Entry point for script execution."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
