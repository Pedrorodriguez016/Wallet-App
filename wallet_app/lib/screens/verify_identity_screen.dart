import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../controllers/wallet_controller.dart';
import '../theme/app_theme.dart';

class VerifyIdentityScreen extends StatelessWidget {
  const VerifyIdentityScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final wallet = context.watch<WalletController>();
    final args =
        ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>?;
    final String openid4vp = args?['openid4vp'] ?? '';

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(30),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: wallet.isLoading
                    ? const CircularProgressIndicator()
                    : const Icon(
                        Icons.fingerprint,
                        size: 64,
                        color: AppColors.primary,
                      ),
              ),
              const SizedBox(height: 32),
              Text(
                "Petició d'identitat",
                style: GoogleFonts.notoSerif(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                "Un servei extern vol verificar la teva identitat. Vols compartir la teva credencial?",
                textAlign: TextAlign.center,
                style: GoogleFonts.manrope(
                  fontSize: 16,
                  color: AppColors.neutral,
                ),
              ),
              const SizedBox(height: 48),
              MaterialButton(
                onPressed: wallet.isLoading
                    ? null
                    : () async {
                        final success = await wallet.handlePresentation(
                          openid4vp,
                        );
                        if (context.mounted) {
                          if (success) {
                            // No hace falta navegar, el RootWrapper nos llevará a Home si limpiamos el estado
                            // Pero para estar seguros y cerrar la pantalla actual:
                            Navigator.of(
                              context,
                            ).popUntil((route) => route.isFirst);
                          } else {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                 content: Text("Error en la verificació"),
                              ),
                            );
                          }
                        }
                      },
                height: 55,
                minWidth: double.infinity,
                color: AppColors.primary,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  "Sí, compartir identitat",
                  style: GoogleFonts.manrope(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: () =>
                    Navigator.of(context).popUntil((route) => route.isFirst),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size(double.infinity, 55),
                  side: const BorderSide(color: AppColors.neutral),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: Text(
                  "No, cancel·lar",
                  style: GoogleFonts.manrope(
                    color: AppColors.neutral,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
