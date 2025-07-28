#!/bin/bash

# Bitcoin_WIF_into_hex.bash: convert from Bitcoin Wallet Import Format (WIF) to hexadicimal number (HEX)
# Examples:
# $ bash Bitcoin_WIF_into_hex.bash "L3wB8ytuxNS3SPX2CJnHqK48Zzqj1AnayDTrJomvNPDxuKvHyvpT" > private_key_bitcoin.hex
# $ bash Bitcoin_WIF_into_hex.bash "xprv9s21ZrQH143K31xYSDQpPDxsXRTUcvj2iNHm5NUtrGiGG5e2DtALGdso3pGz6ssrdK4PFmM8NSpSBHNqPqm55Qn3LqFtT2emdEXVYsCzC2U"
# $ zsh Bitcoin_WIF_into_hex.bash $(< private_key_bitcoin.wif )

declare INPUT_STRING_WIF="$1"
declare -i -r FROM_BASE=58
declare -i -r DIVISOR=16
declare -i remainder=0
declare quotient=""
declare -i subdividend=0
declare quotient_digit=""
declare -r BASE58_CHARSET="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
declare string_of_4digits_numbers=""
declare -i i=0
declare -i j=0
declare result=""

#######################################
# Input validation - min. 51 characters
#######################################
if [[ ${#INPUT_STRING_WIF} -lt 51 ]]; then
  echo "ERROR: The input argument is not 51 characters or longer so it is not a correct string of Bitcoin Core Wallet Import Format (WIF)."
  exit 1
fi

for (( i=0; i<${#INPUT_STRING_WIF}; i++)); do
  for ((j=0; j<${#BASE58_CHARSET}; j++)); do
    if [[ ${INPUT_STRING_WIF:i:1} = ${BASE58_CHARSET:j:1} ]]; then
      printf -v string_of_4digits_numbers "%s%04d" "${string_of_4digits_numbers}" ${j}
      break;
    fi
  done
done
declare dividend=${string_of_4digits_numbers}

while (( ${#dividend} >= ${#DIVISOR} )); do
  for (( position=0; position<${#dividend}; position+=4 )); do
      subdividend=$(( ${remainder} * ${FROM_BASE} + 10#${dividend:position:4} ))
      if [ "${quotient:0:4}" = "0000" ]; then #POSIX conformant if statement
        printf -v quotient "%04d" $(( 10#${subdividend}/${DIVISOR} ))
      else
        printf -v quotient_digit "%04d" $(( 10#${subdividend}/${DIVISOR} ))
        printf -v quotient "%s%s" "${quotient}" "${quotient_digit}"
      fi
      remainder=$(( 10#${subdividend}%${DIVISOR} ))
  done
  printf -v result "%01X%s" "${remainder}" "${result}"
  if [ "${quotient}" = "0000" ]; then
    break
  fi
  dividend=${quotient}
  quotient=""
  remainder=0
done

if [[ ${#INPUT_STRING_WIF} -eq 52 ]]; then
  echo -n "${result:2: -10}"
elif [[ ${#INPUT_STRING_WIF} -eq 51 ]]; then
  echo -n "${result:2: -8}"
else
  echo -n "${result} "
  if [[ ${#INPUT_STRING_WIF} -eq 111 ]]; then
    echo "${result: -72 : -8} ${result: -138 : -74} ${result: -146 : -138} - full hexadecimal number followed by and decomposed into: private key, chain code and the number of the key according to Bitcoin Core's BIP32 Extended Key specification."
  fi
fi
