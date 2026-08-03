import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../models/credential.dart';

class CredentialCard extends StatelessWidget {
  final CredentialModel credential;

  const CredentialCard({super.key, required this.credential});

  @override
  Widget build(BuildContext context) {
    String idDisplay = credential.id;
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
          // Header: type + icon
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  credential.type,
                  style: GoogleFonts.notoSerif(
                    color: AppColors.tertiary,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const Icon(Icons.verified_user, color: AppColors.tertiary),
            ],
          ),
          const SizedBox(height: 30),

          // Emès per a
          _buildFieldLabel("EMÈS PER A"),
          Text(
            credential.name,
            style: GoogleFonts.manrope(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),

          // Títol de l'Esdeveniment
          if (credential.eventName != null &&
              credential.eventName!.isNotEmpty) ...[
            const SizedBox(height: 15),
            _buildFieldLabel("ESDEVENIMENT"),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(
                  Icons.event,
                  color: AppColors.tertiary,
                  size: 16,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    credential.eventName!,
                    style: GoogleFonts.manrope(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
          ],

          // Organitzador
          if (credential.companyName != null &&
              credential.companyName!.isNotEmpty) ...[
            const SizedBox(height: 15),
            _buildFieldLabel("ORGANITZADOR"),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(
                  Icons.business,
                  color: AppColors.tertiary,
                  size: 16,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    credential.companyName!,
                    style: GoogleFonts.manrope(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
          ],

          // Població
          if (credential.poblacion != null &&
              credential.poblacion!.isNotEmpty) ...[
            const SizedBox(height: 15),
            _buildFieldLabel("POBLACIÓ"),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(
                  Icons.location_on,
                  color: AppColors.tertiary,
                  size: 16,
                ),
                const SizedBox(width: 6),
                Text(
                  credential.poblacion!,
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

  Widget _buildFieldLabel(String label) {
    return Text(
      label,
      style: GoogleFonts.manrope(
        color: AppColors.tertiary.withOpacity(0.5),
        fontSize: 10,
        letterSpacing: 1.5,
      ),
    );
  }
}
