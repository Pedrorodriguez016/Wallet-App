import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../controllers/wallet_controller.dart';
import '../theme/app_theme.dart';
import '../models/credential.dart';

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
                        .map((cred) => _buildCredentialCard(cred))
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

  Widget _buildCredentialCard(CredentialModel cred) {
    String idDisplay = cred.id;
    if (idDisplay.length > 20) {
      idDisplay = "ID: ${idDisplay.substring(0, 20)}...";
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.primary, Color(0xFF1E3026)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.2),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                cred.type,
                style: GoogleFonts.notoSerif(
                  color: AppColors.tertiary,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Icon(Icons.verified_user, color: AppColors.tertiary),
            ],
          ),
          const SizedBox(height: 30),
          Text(
            "EMÈS PER A",
            style: GoogleFonts.manrope(
              color: AppColors.tertiary.withOpacity(0.5),
              fontSize: 10,
              letterSpacing: 1.5,
            ),
          ),
          Text(
            cred.name,
            style: GoogleFonts.manrope(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          if (cred.poblacion != null && cred.poblacion!.isNotEmpty) ...[
            const SizedBox(height: 15),
            Text(
              "POBLACIÓ",
              style: GoogleFonts.manrope(
                color: AppColors.tertiary.withOpacity(0.5),
                fontSize: 10,
                letterSpacing: 1.5,
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(
                  Icons.location_on,
                  color: AppColors.tertiary,
                  size: 16,
                ),
                const SizedBox(width: 5),
                Text(
                  cred.poblacion!,
                  style: GoogleFonts.manrope(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 15),
          Text(
            idDisplay,
            style: GoogleFonts.manrope(
              color: Colors.white.withOpacity(0.6),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}
