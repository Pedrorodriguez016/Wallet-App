import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../controllers/wallet_controller.dart';
import '../theme/app_theme.dart';
import '../widgets/credential_card.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final wallet = context.watch<WalletController>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          "El meu Wallet",
          style: GoogleFonts.notoSerif(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: AppColors.primary),
            onPressed: () {
              Navigator.of(context).pushNamed('/settings');
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: AppColors.primary),
            onPressed: () {
              wallet.logout();
              Navigator.of(context).popUntil((route) => route.isFirst);
            },
          ),
        ],
      ),
      body: wallet.isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () => wallet.loadCredentials(),
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  Text(
                    "Les meves credencials",
                    style: GoogleFonts.notoSerif(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (wallet.credentials.isEmpty)
                    _buildEmptyState()
                  else
                    ...wallet.credentials
                        .map((cred) => CredentialCard(credential: cred))
                        .toList(),
                ],
              ),
            ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        children: [
          const SizedBox(height: 50),
          Icon(
            Icons.account_balance_wallet_outlined,
            size: 80,
            color: AppColors.neutral.withOpacity(0.5),
          ),
          const SizedBox(height: 20),
          Text(
            "Encara no tens credencials",
            style: GoogleFonts.manrope(color: AppColors.neutral),
          ),
        ],
      ),
    );
  }
}
