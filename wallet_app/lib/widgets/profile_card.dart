import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../controllers/wallet_controller.dart';
import '../theme/app_theme.dart';

class ProfileCard extends StatelessWidget {
  const ProfileCard({super.key});

  @override
  Widget build(BuildContext context) {
    final wallet = context.watch<WalletController>();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildProfileItem("NOM COMPLET", wallet.userName),
          const Divider(height: 24, thickness: 0.8),
          _buildProfileItem("CORREU ELECTRÒNIC", wallet.userEmail),
          const Divider(height: 24, thickness: 0.8),
          _buildProfileItem("KEYCLOAK USER ID (SUB)", wallet.keycloakUserId),
          const Divider(height: 24, thickness: 0.8),
          _buildProfileItem(
            "IDENTIFICADOR DIGITAL (DID)",
            wallet.userDid.isNotEmpty ? wallet.userDid : "No s'ha generat cap DID encara",
            isMono: true,
          ),
        ],
      ),
    );
  }

  Widget _buildProfileItem(String label, String value, {bool isMono = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: GoogleFonts.manrope(
            fontSize: 11,
            color: AppColors.neutral,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          value,
          style: isMono
              ? GoogleFonts.shareTechMono(
                  fontSize: 14,
                  color: AppColors.primary,
                )
              : GoogleFonts.manrope(
                  fontSize: 15,
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                ),
        ),
      ],
    );
  }
}
